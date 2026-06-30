# PRE-LAUNCH READINESS — Intrinsic IQ

This is the single source of truth for what must be true before this app
is exposed to the public internet. Security, multi-user correctness, and
ops hygiene are NOT versioned features (no V1/V2) — they are part of the
definition of "done" for launch.

Two categories:
- **BLOCKING** — finite, closeable list. Nothing here ships unfinished.
- **CONTINUOUS** — ongoing operating practice that starts at launch and
  never closes. Not a blocker, but must be running from day one.

---

## SECTION A — BLOCKING (must be 100% complete before go-live)

### A1. Multi-User Data Isolation

**ISSUE-004 — Screener progress state is global across all users**
Files: `codes/engine/screener.py`
- `_progress` dict is a single module-level global shared by every visitor
- Fix: per-user progress/polling state; keep `load_universe_background()`
  as a single shared job (don't re-run universe fetch per user) since
  screener *results* are the same for everyone — only progress-viewing
  and "viewed" state need isolation
- Acceptance: two simultaneous users loading the screener never see each
  other's progress messages or interfere with each other's polling state

**ISSUE-005 — Portfolios have no per-user ownership boundary**
Files: `codes/portfolio.py`
- `list_portfolios()`, `load_portfolio()`, `save_portfolio()`,
  `delete_portfolio()` are keyed only by name — any user can read/modify/
  delete any other user's portfolio
- Fix: add `user_id` to every portfolio storage function; change cache key
  from `("portfolio", f"p_{name}")` to `("portfolio", f"{user_id}_p_{name}")`;
  add ownership checks; `list_portfolios()` returns only the caller's own
- Acceptance: user A cannot load/modify/delete user B's portfolio even
  with the exact name; `list_portfolios()` never leaks other users' names

**ISSUE-006 — app.py module-level caches leak state across sessions**
Files: `codes/app.py`
- `_portfolio_cache` mixes ownership-sensitive data across all sessions
- `_analysis_cache`: confirm intentionally global (ticker analysis is not
  user-specific — same ticker = same result for everyone); document this
- `_last_screener_state` / `_last_progress_state`: scope per-user once
  ISSUE-004 lands, or confirm safe to remain global
- Acceptance: no portfolio-membership badge (💼) shown for a portfolio the
  viewing user doesn't own; `_portfolio_cache` invalidates per-user

### A2. Authentication & Payment

**Auth & accounts**
- Login/signup via a managed provider (Auth0 / Clerk / Supabase Auth) —
  do not roll your own auth
- Stable `user_id` available to every Dash callback
- Session cookies: `Secure`, `HttpOnly`, `SameSite=Lax` or `Strict` —
  verify explicitly, don't assume the provider sets these correctly

**Payment / paywall**
- Stripe Checkout + Customer Portal (subscriptions, cancellation, invoices)
- Gate callbacks: free tier (screener browse) vs paid tier (Analyze,
  Portfolio, Factor Lab)
- Do not build billing logic from scratch

### A3. Database & Concurrency

**ISSUE-007 — SQLite will not handle concurrent multi-user writes**
Files: `codes/data/db.py`
- Single-writer SQLite with no connection pooling — will lock/serialize
  under concurrent `upsert()` calls from multiple users analyzing stocks
  simultaneously
- Fix: migrate to Postgres, preserve exact public API (`init_db()`,
  `upsert()`, `get()`, `get_all()`, `delete()`, `count()` — signatures and
  return shapes unchanged so `screener.py`/`app.py` need zero changes)
- Use connection pooling (psycopg pool or SQLAlchemy engine)
- `DATABASE_URL` via environment variable only
- Migration script to copy existing `.cache/value_metrics.db` rows
- Preserve the existing column-whitelist injection guard in `get_all()`
- Acceptance: concurrent writes from multiple simultaneous `analyze_stock()`
  calls don't error or drop data; existing rows migrated, not lost

**Encryption at rest**
- Use a managed Postgres provider with encryption-at-rest enabled by
  default (RDS, Supabase, Render Postgres) — confirm it's on, don't assume

### A4. Security — Application Layer

**Input validation and sanitization**
Files: `codes/app.py`, `codes/portfolio.py`, `codes/data/sec_data.py`
- Ticker symbols, portfolio names, share counts go from raw `dcc.Input`
  values directly into business logic and external API calls with no
  validation
- Fix: whitelist ticker format (alpha, ≤6 chars — reuse the pattern
  already used in `universe.py`'s ticker filtering); validate portfolio
  name length/charset; add a max bound on shares (currently only
  `MIN_SHARES=5`, no max)

**Secrets and error-message hygiene**
Files: `codes/data/api_fetcher.py`, `codes/data/sec_data.py`, `codes/app.py`
- Audit every `except Exception as e: print(...)` / `return {"error": e}`
  path — raw exception text must never reach the user-facing status
  message
- API keys (`FINNHUB_API_KEY`, `TIINGO_API_KEY`, `AV_API_KEY`) must never
  appear in logs or error responses
- Replace print-based logging with structured server-side logging

**Application-layer rate limiting**
Files: `codes/app.py`
- No limit currently on how often a user/IP can trigger Analyze, Load
  Universe, or simulation callbacks
- Fix: add per-user/per-IP rate limiting (Flask-Limiter, since Dash runs
  on Flask) on expensive callbacks

**External API rate-limit protection (user-facing)**
Files: `codes/app.py`, `codes/data/api_fetcher.py`
- SEC EDGAR throttle (3/sec) is shared infra — fine as-is
- Tiingo (500/day) and Finnhub (60/min) free tiers will be exceeded under
  multi-user Analyze traffic
- `RateLimitError` currently surfaces raw to users in `analyze_stock()` —
  fix to show a friendly "try again in Xs" message, or queue requests
- Decide before launch: accept degraded service under load, or pre-pay
  for higher API tiers

### A5. Infrastructure

**Production deployment**
- Replace Dash dev server with gunicorn/waitress behind nginx
- `debug=False` in production
- HTTPS (Let's Encrypt or platform-provided — Render/Railway/Fly.io)
- All API keys via environment variables only — verify none hardcoded or
  committed to git history

**DDoS / WAF protection**
- Put Cloudflare (or provider-native equivalent) in front of the app
- Enable basic WAF rules
- Rate-limit at the edge before requests reach gunicorn
- This is ~30 minutes of setup for very high protective value — no reason
  to skip or defer

### A6. Legal

- Terms of Service + Privacy Policy
- "Not financial advice" disclaimer
- Visible refund/cancellation policy

---

## SECTION B — CONTINUOUS (operating practice from day one, never "finished")

These don't block launch but must be actively running, not deferred
indefinitely:

- **Dependency vulnerability scanning** — `pip-audit` or GitHub Dependabot
  in CI, run before every deploy
- **Error monitoring** — Sentry (or equivalent) wired into the existing
  `_logging_callback` exception handler in `app.py`, live from day one
- **Abuse-pattern monitoring** — watch for scraping, credential stuffing,
  unusual API usage patterns post-launch
- **Incident response plan** — a basic runbook (who gets paged, how to
  rotate a leaked key, how to roll back a bad deploy) — doesn't need to be
  elaborate, needs to exist
- **Regular dependency/framework updates** — Dash, pandas, requests,
  finnhub-python, etc. patched on a cadence, not left stale
- **Periodic access review** — as the user base grows, review who has
  admin/infra access

---

## EXECUTION ORDER

1. ISSUE-004, 005, 006 — multi-user data isolation (sequential: 005 before 006)
2. Auth & accounts
3. ISSUE-007 — Postgres migration + encryption at rest
4. Input validation + secrets hygiene
5. Production deployment (gunicorn, HTTPS, env vars, debug=False)
6. Cloudflare / DDoS / WAF
7. Application-layer rate limiting + external API rate-limit UX
8. Payment/paywall integration
9. Legal pages
10. Stand up Section B continuous practices (monitoring, dependency
    scanning) — these start running *at* launch, not after

## GLOBAL RULE

No item in Section A is deferred to "after launch" or labeled V1/V2.
Section B items begin running at launch and continue indefinitely — they
are not a backlog to clear, they are a standing practice.
