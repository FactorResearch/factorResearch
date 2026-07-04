# Security Remediation — Implementation Guide (for AI agent)

Scope: fixes only for gaps confirmed open in `SECURITY_CHECKLIST_AUDITED.md`. Each item lists exact file(s), what to change, and why. No unrelated refactors.

---

## 1. Pin dependency versions[x]
**File:** `requirements.txt`

Replace unpinned entries with exact/compatible pins (verify current installed versions first via `pip freeze`, then pin):
```
dash==2.17.1
plotly==5.24.1
pandas==2.2.2
numpy==1.26.4
requests==2.32.3
python-dotenv==1.0.1
gunicorn==22.0.0
alpha_vantage==2.3.1
lxml==5.2.2
finnhub-python==2.4.20
psycopg[binary]==3.2.1
python-jose[cryptography]==3.3.0
flask-session==0.8.0
Flask-Limiter==3.8.0
redis==5.0.7
cryptography==42.0.8
bleach==6.1.0
markupsafe==2.1.5
werkzeug==3.0.3
```
Add a CI step (see item 8) to catch drift.

---

## 2. Enforce CSRF on state-changing callbacks
**File:** `codes/app.py`
**Also:** `codes/security.py` (no change needed — `require_csrf` already exists)

Dash callbacks aren't Flask routes, so `@require_csrf` can't decorate them directly. Add explicit checks inside every callback that mutates state:
- `create_portfolio`
- `delete_portfolio`
- `add_to_portfolio`
- `remove_holding`
- `update_shares`
- `run_analysis` (billing/paid action)

Pattern to insert at the top of each of these callback functions:
```python
if not security.verify_csrf_token():
    return <same no-op return shape as existing early-return branches>, "❌ Session expired, please refresh the page."
```
Since Dash doesn't submit a `_csrf_token` form field, switch `verify_csrf_token()` to read from a `dcc.Store` synced via a small clientside callback that stamps `flask.session["_csrf_token"]` into a store on page load, then pass it as a `State` into each mutating callback and compare with `hmac.compare_digest`. Minimal version: add `dcc.Store(id="csrf-token-store")` populated once via a `/csrf-token` Flask route, and validate that store's value against `security.get_csrf_token()` at the top of each callback above.

---

## 3. Wire up audit logging
**File:** `codes/app.py`

Add `security.audit_log_access(...)` calls at these existing points (functions already exist in `security.py`, just unused):
- `add_to_portfolio` — after successful `portfolio_engine.add_holding`: `action="WRITE", resource=f"portfolio:{port_name}"`
- `remove_holding` — after successful removal: `action="DELETE"`
- `update_shares` — after successful update: `action="WRITE"`
- `delete_portfolio` — after deletion: `action="DELETE"`
- `run_analysis` — on successful analysis: `action="READ", resource=f"analysis:{symbol}"`

Pass `user_id=uid` (or `_get_user_id()`), `success=True/False` matching the branch taken.

---

## 4. Sanitize free-text output before rendering
**File:** `codes/app.py`

Only one true free-text user input reaches rendered HTML: portfolio names (`portfolio-create-name`, `portfolio-new-name`) and company names pulled from `analysis["name"]` (SEC-sourced, semi-trusted).

Wrap portfolio name display sites with `security.sanitize_string(name, max_length=32)` before putting into `html.Span`/`html.Div`:
- `render_portfolio_holdings` — `active` (portfolio name header)
- `refresh_portfolio_dropdowns` — dropdown labels
- `_build_comparison_view` — portfolio name headers/banners

This is defense-in-depth since Dash already escapes string children; do NOT skip because "Dash escapes it" — sanitize at the boundary so it's independent of frontend framework.

---

## 5. Move rate limiter + shared state to Redis (multi-worker safety)
**Files:** `codes/app.py`, `codes/core/redis_client.py` (already has `get_redis`, `json_get`, `json_set`)

Replace `_RATE_LIMIT_STORE` dict-based `_check_rate_limit` with a Redis-backed version:
```python
def _check_rate_limit(action, calls, period_seconds, key=None):
    key = key or _get_user_id()
    r = get_redis()
    if r is None:
        # fallback: existing in-memory logic (dev-only)
        ...
    redis_key = f"rl:{action}:{key}"
    now = int(_time.time())
    pipe = r.pipeline()
    pipe.zremrangebyscore(redis_key, 0, now - period_seconds)
    pipe.zadd(redis_key, {str(now): now})
    pipe.zcard(redis_key)
    pipe.expire(redis_key, period_seconds)
    _, _, count, _ = pipe.execute()
    if count > calls:
        raise RateLimited(retry_after=period_seconds)
```
`screener._progress` and `_analysis_cache` already have partial Redis sync (`_sync_progress_to_redis`) — confirm `_analysis_cache` also checks Redis first before falling back to local dict, mirroring the pattern in `screener.py`.

---

## 6. Add CORS policy
**File:** `codes/app.py`

Add after `server = app.server`:
```python
from flask_cors import CORS
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").split(",") if os.environ.get("ALLOWED_ORIGINS") else []
if ALLOWED_ORIGINS:
    CORS(server, origins=ALLOWED_ORIGINS, supports_credentials=True)
```
Add `flask-cors` to `requirements.txt` (pinned, e.g. `flask-cors==4.0.1`). Document `ALLOWED_ORIGINS` in `.env.example`. If the app has no cross-origin API consumers, explicitly leave CORS disabled (default same-origin) rather than wildcarding `*`.

---

## 7. Build real ToS / Privacy Policy pages
**File:** `codes/app.py`

Replace the placeholder `<a href="/terms">` / `<a href="/privacy">` footer links with real Flask routes registered on `server`:
```python
@server.route("/terms")
def terms_page():
    return flask.render_template_string(TERMS_HTML)

@server.route("/privacy")
def privacy_page():
    return flask.render_template_string(PRIVACY_HTML)
```
Content itself (`TERMS_HTML`, `PRIVACY_HTML`) is a legal-drafting task, not a code task — flag to a human/legal reviewer rather than auto-generating boilerplate. At minimum include: no-financial-advice disclaimer (already present in UI), data collected, third-party processors (Auth0/Stripe/Tiingo/Finnhub/SEC), refund policy, contact email.

---

## 8. CI dependency vulnerability scanning
**New file:** `.github/workflows/security-scan.yml` (or equivalent CI config for the platform in use)

```yaml
name: security-scan
on: [push, pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: pip install pip-audit bandit
      - run: pip-audit -r requirements.txt
      - run: bandit -r codes/ -ll
```
Fails the build on known CVEs or high-severity bandit findings.

---

## Out of scope for AI implementation (flag to human)
- MFA enforcement — configured in the Auth0/Clerk/Supabase dashboard, not in this repo.
- Data retention/deletion (GDPR/CCPA) — requires a product/legal decision on retention windows before coding cascading-delete logic.
- TLS certificate / reverse proxy — infra, not application code.

---

## Suggested implementation order
1. Item 1 (pin deps) — zero risk, do first.
2. Item 7 (legal pages) — needs content from a human before wiring routes.
3. Item 6 (CORS) — needs `ALLOWED_ORIGINS` decision from product owner.
4. Item 5 (Redis rate limiter) — needed before any multi-worker deploy.
5. Item 2 (CSRF enforcement) — highest engineering effort, do after 1/5.
6. Item 3 (audit logging) — straightforward, low risk.
7. Item 4 (output sanitization) — low risk, quick.
8. Item 8 (CI scanning) — add once repo has a CI provider confirmed.