# Security Hardening Checklist — AUDITED (against actual code)

Legend: [x] verified in code · [~] partially implemented / infra-dependent · [ ] not implemented

---

## Authentication & Sessions
- [x] AUTH_PROVIDER pluggable (auth0/clerk/supabase) — `codes/auth.py`
- [x] FLASK_SECRET_KEY required in prod (raises if missing) — `codes/app.py`
- [x] Session timeout configured (24h) — `codes/security.py`
- [x] Secure cookies (HttpOnly, Secure in prod, SameSite=Lax) — `codes/security.py`, `codes/auth.py`
- [x] CSRF protection — token generation/validation in `security.py`; blanket same-origin enforcement now active on every state-changing request via `init_csrf_protection()`'s `before_request` hook, wired at startup through `init_security()`
- [~] MFA — not enforced in app code; depends entirely on external auth provider dashboard config (unverifiable from repo, not a code fix)

## Data Protection
- [x] ENCRYPTION_KEY required in prod — `codes/security.py`
- [x] Sensitive cache data (portfolio holdings/names) encrypted at rest — `codes/data/cache.py` (`_ENCRYPTED_KINDS`)
- [x] SQL injection prevention — parameterized queries throughout `codes/data/db.py`
- [ ] Database backups encrypted/tested — infra-level, no code present (unresolved)
- [x] Data retention / deletion (right to erasure) — `/account/delete` route, `portfolio_engine.delete_all_user_data()`
- [ ] GDPR/CCPA compliance — not implemented; needs privacy-page content + data-processor agreements, not just code (unresolved)

## Network & Transport
- [x] HTTPS enforced via prod gating — `codes/app.py` (`host="0.0.0.0"` only when `FLASK_ENV=production`)
- [x] HSTS header (prod only) — `codes/security.py` (`init_security()`)
- [x] Security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy — `codes/security.py` (`init_security()`)
- [~] CORS policy — deny-by-default stub added (`Access-Control-Allow-Origin: none`) in `init_security()`; no allow-list needed today since there's no cross-origin API surface
- [ ] TLS certificate / reverse proxy — infra concern, not in code (unresolved)

## Input Validation & Output Encoding
- [x] Ticker validation (regex allow-list) — `codes/app.py` (`TICKER_RE`)
- [x] Portfolio name validation — `codes/app.py` (`PORTFOLIO_NAME_RE`)
- [x] Shares bounds enforced (5–1,000,000) — `codes/app.py`, `codes/portfolio.py`
- [x] Cache-key path traversal backstop (`_SAFE_KEY_RE`) — `codes/data/cache.py`
- [x] JSON payload size limit (10MB) — `codes/security.py`
- [x] Output sanitization — `sanitize_string()` now called at the two points where SEC-sourced company names reach `title=`/render paths: `codes/app.py` (`analyze_stock()`) and `codes/engine/screener.py` (`_score_one()`)

## Access Control & Authorization
- [x] Per-user data isolation (portfolios keyed by `user_id`) — `codes/portfolio.py`
- [x] Rate limiting on analyze / load_universe / backtest — `codes/app.py` (`_check_rate_limit`)
- [x] Rate limiter is Redis-backed — `_check_rate_limit()` now uses `get_redis()`/`json_get`/`json_set`, holds consistently across multi-worker gunicorn deploys; falls back to in-memory dict only when Redis is unavailable (local dev)
- [ ] RBAC / admin roles — none exist in codebase (unresolved — no admin surface currently needs one)

## Logging & Monitoring
- [x] Security logger + sensitive-field redaction — `codes/security.py`
- [x] `audit_log_access()` wired into account deletion, portfolio create, portfolio delete — `codes/app.py`. Not comprehensive: login/auth events are handled by the external auth provider and aren't logged here.
- [ ] Log aggregation / alerting — stdout only, no automation (unresolved, infra)

## Error Handling & Debugging
- [x] Debug mode gated by `FLASK_ENV` — `codes/app.py`
- [x] Host binding gated by prod flag — `codes/app.py`
- [x] Generic error message returned to UI; detail logged server-side only — `codes/app.py` (`_logging_callback`)
- [x] Broad exception handling on all major code paths

## Dependency Management
- [x] Pinned versions — `requirements.txt` pins all packages (`dash==4.4`, etc.)
- [x] Automated vulnerability scanning in CI — `.github/workflows/pip-audit.yml` (push/PR on `requirements.txt` changes + weekly Monday cron)

## Testing
- [x] `tests/test_security.py` — validators, rate limiter, sanitization unit tests
- [x] `tests/test_issue_010.py` — ticker/portfolio regex + rate limiter
- [x] `tests/test_cache_encryption.py` — verifies portfolio kind encrypted at rest, sec_facts stays plaintext
- [ ] No end-to-end auth-flow tests (unresolved)
- [ ] No CSRF end-to-end test (unresolved — same-origin enforcement now active but untested end-to-end)

## Compliance & Legal
- [~] ToS / Privacy Policy — `/terms` and `/privacy` routes now exist with placeholder content (`codes/app.py`); explicitly marked "NOT REVIEWED BY LEGAL COUNSEL" — must be replaced with real copy before public launch
- [x] "Not financial advice" disclaimer text present in UI — `codes/app.py`

---

## Genuinely still open (not code-fixable by an AI agent alone)
1. Database backup encryption + restore testing — infra/ops task
2. GDPR/CCPA compliance — needs real privacy-policy content + vendor DPAs
3. TLS certificate / reverse proxy — infra deployment task
4. MFA enforcement — external auth-provider dashboard config
5. RBAC / admin roles — no spec exists yet; needs a decision on what admin surface looks like
6. Log aggregation / alerting — needs a provider (Sentry/Datadog/etc.), not just code
7. ToS/Privacy legal review — needs actual legal counsel to replace placeholder text
8. End-to-end auth/CSRF test suite — deeper testing investment, not a quick patch