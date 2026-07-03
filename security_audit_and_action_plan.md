# Intrinsic IQ — Security Audit & Production Readiness Action Plan

**Scope:** `codes/app.py`, `codes/portfolio.py`, `codes/data/*`, `codes/engine/*`, `codes/models/*`, `Publish.md`, `KNOWN_ISSUES.md`
**Method:** Manual static review of full source (no live pentest, no dependency scan — see §6).
**Context:** Current design has no user accounts (anonymous Flask-session UUID only), file/SQLite storage, single-process Dash dev server. Goal: get to a state that is safe for public web use *and* sets up cleanly for future bank/brokerage integration (Plaid/Alpaca-style), which implies SOC 2 / GLBA-adjacent expectations even before any account-linking exists.

---

## 1. Executive Summary

Publish.md already tracks 10 real issues (ISSUE_004–013) and 3 are marked closed. That list is good but **incomplete** — it was written before some of the current code (e.g. `debug=True`, raw cache-key construction) was reviewed against actual attack surface. This audit found **7 additional issues**, two of which are **Critical** and should block any public deployment regardless of the Publish.md timeline:

| # | Finding | Severity | Tracked in Publish.md? |
|---|---|---|---|
| NEW-1 | Path traversal via unsanitized cache keys (ticker/portfolio name → filename) | **Critical** | No |
| NEW-2 | `debug=True` + bind `0.0.0.0` = remote code execution via Werkzeug debugger | **Critical** | Only implied by ISSUE_011 |
| NEW-3 | No security headers (CSP/HSTS/X-Frame-Options/X-Content-Type-Options) | High | Only implied by ISSUE_011 |
| NEW-4 | In-memory global state breaks under multi-worker/multi-instance deploy | High | No |
| NEW-5 | User-supplied ticker interpolated unvalidated into outbound API URLs | Medium | Partially — ISSUE_010 |
| NEW-6 | Raw exception text returned to the browser | Medium | Partially — ISSUE_010 |
| NEW-7 | Session cookie has no `Secure`/`SameSite` hardening pre-auth | Medium | Only implied by ISSUE_008 |

Everything already in Publish.md (ISSUE_004–014) remains valid and is folded into the action plan below with re-prioritization.

**Bottom line:** the app is not safe to expose publicly today. NEW-1 and NEW-2 alone allow an unauthenticated visitor to potentially read/write arbitrary files on the host and, via the debugger, execute arbitrary Python. Both are cheap to fix (hours, not weeks) and should happen before anything else, including auth.

---

## 2. Critical Findings (New)

### NEW-1 — Path traversal via cache keys (CRITICAL)
**File:** `codes/data/cache.py` (`_path()`), consumed by `codes/app.py`, `codes/portfolio.py`, `codes/engine/screener.py`

```python
def _path(kind: str, key: str) -> Path:
    return CACHE_DIR / f"{kind}-{key.lower()}.json"
```

`key` is never validated. It comes directly from:
- the **ticker input box** (`symbol = ticker.strip().upper()` in `run_analysis`) → `cache.read("analysis", symbol)` / `cache.write(...)`
- the **portfolio name input** (`portfolio-create-name`) → `cache.write("portfolio", f"{user_id}_p_{name}", ...)`

A string like `../../../../tmp/evil` in either field becomes part of the path passed to `Path.__truediv__`, which happily resolves `..` segments. This is a classic path-traversal primitive that can be used to:
- **Read** arbitrary `.json`-readable files on the host by crafting a ticker that maps outside `.cache/` (limited to files ending in a name we control + `.json`, but still exfiltration-capable if any sensitive config lives nearby).
- **Write/overwrite** files outside `.cache/` (the JSON cache writer will happily serialize attacker-influenced data), which combined with NEW-2 is a path to full compromise.

**Fix:** allow-list ticker format (`^[A-Z]{1,6}(\.[A-Z])?$`), portfolio names (`^[A-Za-z0-9 _-]{1,32}$`), and — defense in depth — sanitize inside `cache._path()` itself (reject any key containing `/`, `\`, or `..` regardless of caller). Never trust caller-side validation alone for a shared low-level module.

### NEW-2 — `debug=True` bound to `0.0.0.0` (CRITICAL)
**File:** `codes/app.py`, bottom: `app.run(host="0.0.0.0", debug=True, port=8050)`

Flask/Werkzeug's interactive debugger is enabled and reachable from any network interface. If any unhandled exception occurs, the debugger console is exposed; if the debugger PIN protection is bypassed or not effectively randomized in the deployment environment, this is a direct path to **remote code execution**. Combined with the many `except Exception` paths that already print tracebacks, this stack throws often — increasing exposure.

**Fix:** `debug=False` in any environment reachable from the internet; run behind gunicorn/waitress (already scoped as ISSUE_011); keep `debug=True` only for `127.0.0.1`-bound local dev.

---

## 3. High/Medium Findings (New)

### NEW-3 — No security headers
`@server.after_request def _log_errors(response): return response` is a no-op (misleading name — it doesn't log anything). No CSP, no `Strict-Transport-Security`, no `X-Frame-Options`, no `X-Content-Type-Options`. Add `flask-talisman` or set headers manually in that same hook.

### NEW-4 — Global in-memory state won't survive horizontal scaling
`_progress`, `_analysis_cache`, `_portfolio_cache_by_session`, `_last_screener_state`, `_spy_history` are plain Python module-level dicts/vars. The moment this runs under gunicorn with >1 worker (needed for ISSUE_011), each worker has its **own** copy — screener progress, portfolio caches, and analysis caches will silently disagree between requests hitting different workers. This isn't a security bug per se, but it becomes one once auth/billing are added, because tier-gating decisions or cached "ownership" data could become inconsistent across workers.
**Fix:** move shared mutable state to Redis (progress, session-scoped caches) before scaling past 1 worker.

### NEW-5 — Unvalidated ticker flows into outbound URLs
`codes/data/api_fetcher.py`: `f"{TIINGO_BASE_URL}/{symbol.lower()}/prices"` and similar in Finnhub/Alpha Vantage paths. `symbol` is user input with no format check before hitting `_score_one()` / `analyze_stock()`. Low practical SSRF risk today (fixed base URL prefix), but a malformed ticker can still manipulate the request path or waste API quota. Same root cause as NEW-1 — fix once at the input boundary (ticker regex) and it closes both.

### NEW-6 — Raw exception strings surfaced to the client
Multiple places: `return {"error": f"SEC EDGAR error: {e}"}`, `return {"error": str(e)}` for `RateLimitError`. Exception text can include internal details (host names, library internals). Not devastating today since there's no auth/secret material in these exceptions, but it's bad hygiene and explicitly called out as an ISSUE_010 acceptance criterion — enforce a generic user-facing message + full detail only in server logs.

### NEW-7 — Session cookie not hardened
`server.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24)`. Two problems:
1. If the env var is unset, a new random key is generated **every process restart**, silently invalidating all sessions (availability issue, and it hides the fact that the required env var is missing — should fail loudly instead).
2. No `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY` (Flask defaults `HttpOnly=True`, but `Secure` and `SameSite` are not set), so the session cookie can be sent over plain HTTP and is more exposed to CSRF than necessary.

**Fix:** require `FLASK_SECRET_KEY` at boot (raise if missing in prod), set `SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_SAMESITE="Lax"`.

---

## 4. Existing Known Issues (Publish.md) — Re-validated

All of these are real and still needed; re-prioritized in §5.

| ID | Status | Note from this review |
|---|---|---|
| ISSUE_004 | [x] closed | Confirmed: per-session progress snapshot correctly separated from shared job state. |
| ISSUE_005 | [x] closed | Confirmed: `portfolio.py` keys are `user_id`-scoped. Still vulnerable to NEW-1 (path traversal) at the storage layer regardless. |
| ISSUE_006 | [x] closed | Confirmed: `_portfolio_cache_by_session` is session-scoped; `_analysis_cache` intentionally shared (correct — it's ticker-deterministic public data). |
| ISSUE_007 | [x] closed | SQLite `check_same_thread=False` + no pooling — will fail under real concurrent write load. Confirmed still single-writer risk. |
| ISSUE_008 | Open | No auth exists at all today — confirmed. This is the biggest structural gap for "user registration and data storage." |
| ISSUE_009 | Open | No billing/tier enforcement — confirmed, not built. |
| ISSUE_010 | Open | Confirmed — no input validation anywhere (tickers, portfolio names, shares are only range-checked, not type/format-checked at the edge). |
| ISSUE_011 | Open | Confirmed `debug=True`, dev server, no TLS/reverse proxy. |
| ISSUE_012 | Open | Confirmed `RateLimitError` messages currently reach `status-msg` in the UI verbatim — ties to NEW-6. |
| ISSUE_013 | Open | No ToS/Privacy Policy/disclaimers present in `app.layout`. |
| ISSUE_014 | Open | Confirmed — no TTL/eviction on `_portfolio_cache_by_session` or `_user_progress`. `clear_user_progress()` exists but is never called from anywhere in `app.py`. |

---

## 5. Prioritized Action Plan

### Phase 0 — Stop-the-bleeding (before *any* public exposure, days not weeks)[x]
1. **NEW-1**: Add strict allow-list validation for ticker, portfolio name, and any other string used as a cache key; sanitize inside `cache._path()` itself as a hard backstop.
2. **NEW-2**: Set `debug=False`; if local debugging is still needed, gate it behind `FLASK_ENV`/an explicit local-only flag, never bound to `0.0.0.0`.
3. **NEW-6 / ISSUE_012**: Replace all `{e}`-in-message returns to the UI with generic messages; log full detail server-side only.
4. **NEW-7**: Require `FLASK_SECRET_KEY` (fail startup if missing outside local dev); set `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`.

### Phase 1 — Data isolation & hygiene (already mostly scoped in Publish.md)[x]
5. ISSUE_010: Full input validation layer (ticker regex, portfolio name regex, shares bounds) — this also structurally closes NEW-5.
6. ISSUE_014: Add TTL sweep for `_portfolio_cache_by_session` / `_user_progress`; wire `clear_user_progress()` to an actual disconnect/logout hook.
7. NEW-3: Add security headers (Talisman or manual) + confirm CSP doesn't break Plotly/Dash inline scripts (will need a nonce or relaxed `script-src` for Dash's own bundles).

### Phase 2 — Real authentication & authorization (this is the big structural change)[x]
8. ISSUE_008: Integrate Auth0/Clerk/Supabase Auth. Replace the anonymous `flask.session["_uid"]` UUID with a real authenticated `user_id` claim, but **keep the same `user_id`-scoped storage pattern** already built in `portfolio.py` — this was designed well, it just needs a trustworthy identity behind it.
9. Add authorization checks at the callback layer: every portfolio read/write must confirm the authenticated user owns that `user_id` prefix (currently implicit via session cookie; needs to become explicit once real accounts exist, especially for account recovery/merge flows).
10. NEW-4: Move `_progress`, session-scoped caches to Redis so auth/tier state and screener progress are consistent across workers — do this *before* enabling >1 gunicorn worker.

### Phase 3 — Database & infra hardening
11. ISSUE_007: Migrate `value_metrics` and portfolio/analysis JSON blobs off flat files + single-writer SQLite to Postgres (or at minimum SQLite with WAL mode + a proper connection pool) — preserve the existing `db.py` function signatures.
12. ISSUE_011: gunicorn/waitress behind nginx/Cloudflare, TLS everywhere, secrets via environment only (see Phase 5 for secrets manager upgrade).
13. Add **encryption at rest** for anything that becomes personally identifiable once accounts exist (email, name, portfolio holdings) — disk-level (EBS/RDS encryption) is the minimum bar; field-level encryption for anything brokerage-adjacent later.

### Phase 4 — Billing & legal
14. ISSUE_009: Stripe Checkout + Customer Portal, tier gating enforced server-side in callbacks (not just hidden in the UI).
15. ISSUE_013: ToS, Privacy Policy, "not financial advice" disclaimer, refund policy — all linked pre-signup.

### Phase 5 — Compliance runway for future bank/brokerage integration
These aren't urgent for launch but should shape decisions made in Phases 2–4 so you don't have to redo them later:

| Requirement | Why it matters for bank/brokerage partners | What to do now |
|---|---|---|
| Audit logging | Brokerage partners (Plaid, Alpaca, DTCC-adjacent rails) expect immutable, timestamped logs of who accessed what | Start logging auth events, portfolio mutations, and data-access events now, even before a partner asks — retrofit is painful |
| MFA | Standard expectation for anything touching financial account linkage | Pick an auth provider (Phase 2) that supports MFA out of the box (Auth0/Clerk/Supabase all do) |
| Secrets management | GLBA/SOC 2 vendor reviews will ask where API keys and (eventually) OAuth tokens live | Move from raw env vars to AWS Secrets Manager / Vault once you have real user data, not just market-data API keys |
| Data retention & deletion | GDPR/CCPA "right to erasure"; brokerage partners will require you to propagate deletion requests | Design account deletion (cascading delete across portfolios, analysis cache, SQLite rows) as part of Phase 2, not bolted on later |
| Least-privilege OAuth scopes | When you eventually connect to a brokerage API (read-only holdings vs. trading) | Architect the credential-storage layer assuming encrypted, scoped, revocable tokens from day one |
| SOC 2 readiness | Partners will ask for a SOC 2 Type II report or equivalent before integrating | Start collecting evidence (access reviews, change management, incident response runbook) once Phase 2–3 land; a Type II report needs months of evidence history, so the clock should start early |
| Penetration testing cadence | Expected before any brokerage data-sharing agreement | Schedule an external pentest after Phase 3, then annually |

### Continuous (start at launch, never "done")
- Dependency scanning (`pip-audit`/Dependabot) in CI.
- Error monitoring (Sentry) wired into the existing `_log_errors` hook (rename it to reflect what it actually does once it's doing something).
- Abuse/rate-limit monitoring on `analyze_stock`, `load_universe`, simulation endpoints.
- Periodic access reviews once real accounts/roles exist.

---

## 6. What this audit does *not* cover
- No dependency/CVE scan was run (no `requirements.txt` was in the provided context) — run `pip-audit` against the real lockfile before launch.
- No live penetration test — this is a code review only.
- No review of the (not-yet-built) Stripe/auth-provider integration code, since it doesn't exist yet — re-audit once Phase 2/4 land.

## 7. Suggested Sequencing Summary
```
Phase 0  (days)    → NEW-1, NEW-2, NEW-6, NEW-7        [BLOCKS any public exposure]
Phase 1  (1-2 wks) → ISSUE_010, ISSUE_014, NEW-3
Phase 2  (2-4 wks) → ISSUE_008, NEW-4                  [BLOCKS real user registration]
Phase 3  (2-3 wks) → ISSUE_007, ISSUE_011, encryption-at-rest
Phase 4  (1-2 wks) → ISSUE_009, ISSUE_013
Phase 5  (ongoing) → audit logging, MFA, secrets mgmt, retention policy, SOC 2 evidence
```
