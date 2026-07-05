# Security Hardening Checklist — AUDITED (against actual code)

Legend: [x] verified in code · [~] partially implemented / defined-but-unused · [ ] not implemented

---

## Authentication & Sessions
- [x] AUTH_PROVIDER pluggable (auth0/clerk/supabase) — `codes/auth.py`
- [x] FLASK_SECRET_KEY required in prod (raises if missing) — `codes/app.py`
- [x] Session timeout configured (24h) — `codes/security.py`
- [x] Secure cookies (HttpOnly, Secure in prod, SameSite=Lax) — `codes/security.py`, `codes/auth.py`
- [x] CSRF protection — token generation/validation exists in `security.py`, but `require_csrf` decorator is **never applied** to any Dash callback or route
- [ ] MFA — not enforced in app code; depends entirely on external auth provider dashboard config (unverifiable from repo)

## Data Protection
- [x] ENCRYPTION_KEY required in prod — `codes/security.py`
- [x] Sensitive cache data (portfolio holdings/names) encrypted at rest — `codes/data/cache.py` (`_ENCRYPTED_KINDS`)
- [x] SQL injection prevention — parameterized queries throughout `codes/data/db.py`
- [ ] Database backups encrypted/tested — infra-level, no code present
- [ ] Data retention / deletion (right to erasure) — not implemented
- [ ] GDPR/CCPA compliance — not implemented

## Network & Transport
- [x] HTTPS enforced via prod gating — `codes/app.py` (`host="0.0.0.0"` only when `FLASK_ENV=production`)
- [x] HSTS header (prod only) — `codes/security.py`
- [x] Security headers: X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy, Permissions-Policy — `codes/security.py`
- [ ] CORS policy — not configured anywhere in codebase
- [ ] TLS certificate / reverse proxy — infra concern, not in code

## Input Validation & Output Encoding
- [x] Ticker validation (regex allow-list) — `codes/app.py` (`TICKER_RE`), `codes/security.py`
- [x] Portfolio name validation — `codes/app.py` (`PORTFOLIO_NAME_RE`)
- [x] Shares bounds enforced (5–1,000,000) — `codes/app.py`, `codes/portfolio.py`
- [x] Cache-key path traversal backstop (`_SAFE_KEY_RE`) — `codes/data/cache.py` (NEW-1 fixed)
- [x] JSON payload size limit (10MB) — `codes/security.py`
- [~] Output sanitization — `sanitize_string()` exists but is **not called** anywhere in `app.py`'s render paths; relies solely on Dash's built-in auto-escaping

## Access Control & Authorization
- [x] Per-user data isolation (portfolios keyed by `user_id`) — `codes/portfolio.py`
- [x] Rate limiting on analyze / load_universe / backtest — `codes/app.py` (`_check_rate_limit`)
- [~] Rate limiter is in-memory only (`_RATE_LIMIT_STORE` dict) — will NOT hold limits consistently across multiple gunicorn workers (NEW-4, unresolved)
- [ ] RBAC / admin roles — none exist in codebase

## Logging & Monitoring
- [x] Security logger + sensitive-field redaction — `codes/security.py`
- [~] `audit_log_access()` / `log_security_event()` defined but **not called** from any callback in `app.py` — no actual audit trail is being produced today
- [ ] Log aggregation / alerting — stdout only, no automation

## Error Handling & Debugging
- [x] Debug mode gated by `FLASK_ENV` — `codes/app.py` (`debug=not _is_prod`) — **NEW-2 fixed**
- [x] Host binding gated by prod flag (`127.0.0.1` outside prod, `0.0.0.0` only in prod) — **NEW-2 fixed**
- [x] Generic error message returned to UI; callback wrapper raises "Internal server error", logs detail server-side only — `codes/app.py` (`_logging_callback`)
- [x] Broad exception handling on all major code paths

## Dependency Management
- [ ] **Pinned versions — `requirements.txt` has NO version pins** (`dash`, `plotly`, `pandas`, `numpy`, etc. all unpinned). Real, unresolved gap.
- [ ] Automated vulnerability scanning (`pip-audit`/`safety`) in CI — not present in repo

## Testing
- [x] `tests/test_security.py` — validators, rate limiter, sanitization unit tests
- [x] `tests/test_issue_010.py` — ticker/portfolio regex + in-memory rate limiter
- [x] `tests/test_cache_encryption.py` — verifies portfolio kind encrypted at rest, sec_facts stays plaintext
- [ ] No end-to-end auth-flow tests
- [ ] No CSRF end-to-end test (token generation only, no enforcement test — because enforcement isn't wired up)

## Compliance & Legal
- [ ] **ToS / Privacy Policy — `/terms` and `/privacy` are placeholder links only**; pages don't exist (`codes/app.py` footer). ISSUE_013 still open.
- [x] "Not financial advice" disclaimer text present in UI — `codes/app.py`

---

## Net-new items confirmed fixed since last audit
- **NEW-1** (path traversal via cache keys) — fixed: `_SAFE_KEY_RE` allow-list in `cache._path()`
- **NEW-2** (`debug=True` on `0.0.0.0`) — fixed: gated by `FLASK_ENV`
- **NEW-7** (session cookie hardening) — fixed: `FLASK_SECRET_KEY` required in prod, `SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE` set in `security.py`

## Still open / real gaps
1. Dependency versions unpinned in `requirements.txt`
2. CSRF enforcement not wired to any callback (mechanism exists, unused)
3. Audit logging not wired to any callback (mechanism exists, unused)
4. Output sanitization not called before rendering (relying on Dash auto-escape only)
5. In-memory rate limiter breaks under multi-worker deploy (NEW-4)
6. CORS policy absent
7. ToS/Privacy pages don't exist (only linked)
8. No automated dependency vulnerability scanning in CI