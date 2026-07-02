# ================================
# PRE-LAUNCH READINESS — Intrinsic IQ (AI-Optimized Spec)
# ================================

pre_launch_readiness:

  meta:
    purpose: >
      Defines all blocking and continuous requirements for production launch.

  rule:
    - BLOCKING items must be 100% complete before launch
    - CONTINUOUS items must start at launch and never be considered complete
    - No V1/V2 deferrals for BLOCKING items
    - once complete front of each issue id add [x]


# ================================
# ISSUE SCHEMA (STANDARD TEMPLATE)
# ================================

issue_schema:

  id: "ISSUE-XXX"
  title: "string"
  category: "data-isolation | auth | db | security | infra | billing | api | legal"

  files:
    - "path/to/file"

  problem: "string"
  root_cause: "string"
  required_fix: "string"

  constraints:
    - "string"

  acceptance_criteria:
    - "string"

  risk_if_not_fixed: "high | medium | low"


# ================================
# SECTION A — BLOCKING (MUST COMPLETE BEFORE LAUNCH)
# ================================

blocking:


  # ----------------------------
  # DATA ISOLATION
  # ----------------------------

  ISSUE_004[x]:

    title: "Screener state is globally shared across users"
    category: data-isolation

    files:
      - codes/engine/screener.py

    problem: "_progress is a module-level global shared across users"

    root_cause: "No per-user session isolation for progress tracking"

    required_fix: >
      Introduce per-user progress state store.
      Keep load_universe_background() as a shared singleton job.
      Only UI progress state must be per-user.

    constraints:
      - Universe fetch remains global/shared (same data for all users)

    acceptance_criteria:
      - Two concurrent users never see each other's progress
      - No cross-session polling interference

    risk_if_not_fixed: HIGH


  ISSUE_005[x]:

    title: "Portfolio data has no ownership boundary"
    category: data-isolation

    files:
      - codes/portfolio.py

    problem: "Portfolio CRUD is keyed only by name"

    root_cause: "Missing user_id scoping in storage layer"

    required_fix: >
      Add user_id to all portfolio operations and cache keys.
      Example: p_{name} → {user_id}_p_{name}

    constraints:
      - list_portfolios() must return only user-owned data

    acceptance_criteria:
      - User A cannot access User B portfolios under any condition

    risk_if_not_fixed: HIGH


  ISSUE_006[x]:

    title: "App-level cache leaks cross-user state"
    category: data-isolation

    files:
      - codes/app.py

    problem: "_portfolio_cache may mix data across users"

    root_cause: "Shared global in-memory cache"

    required_fix: >
      Scope all sensitive caches by user_id.
      Evaluate whether analysis cache can remain global (ticker-based purity).

    constraints:
      - Analysis cache may remain global if deterministic per ticker

    acceptance_criteria:
      - No incorrect ownership indicators in UI
      - No cross-user cache hits

    risk_if_not_fixed: HIGH


  ISSUE_014[x]:

    title: "Per-session caches grow unbounded (memory leak)"
    category: data-isolation

    files:
      - codes/app.py
      - codes/engine/screener.py

    problem: >
      _portfolio_cache_by_session (app.py) and _user_progress (screener.py)
      are plain dicts keyed by session id with no eviction. Entries persist
      for the life of the process even after a session/browser tab ends.

    root_cause: "No TTL or cleanup hook tied to session expiry for these per-session stores"

    required_fix: >
      Add periodic eviction (e.g. TTL-based sweep or LRU cap) for
      _portfolio_cache_by_session and _user_progress. Trigger cleanup on
      known disconnect points where available (clear_user_progress already
      exists for screener.py but is not called anywhere).

    constraints:
      - Does not change per-user isolation behavior (ISSUE-004/006 remain intact)
      - No change to storage keys or public function signatures

    acceptance_criteria:
      - Long-running server with many short-lived sessions shows bounded memory growth
      - Stale session entries are removed after a defined TTL

    risk_if_not_fixed: LOW


  # ----------------------------
  # DATABASE
  # ----------------------------

  ISSUE_007[x]:

    title: "SQLite not safe for concurrent multi-user writes"
    category: db

    files:
      - codes/data/db.py

    problem: "SQLite single-writer model breaks under concurrency"

    root_cause: "No connection pooling or server-grade database layer"

    required_fix: >
      Migrate to Postgres with connection pooling.
      Preserve DB API exactly:
        init_db, upsert, get, get_all, delete, count

    constraints:
      - No changes to app-level logic allowed
      - Must preserve schema and whitelist safeguards

    acceptance_criteria:
      - No locking or write failures under concurrent usage
      - Full migration from existing SQLite DB

    risk_if_not_fixed: HIGH


  # ----------------------------
  # AUTHENTICATION & BILLING
  # ----------------------------

  ISSUE_008[x]:

    title: "No managed authentication in place"
    category: auth

    files:
      - codes/app.py
      - codes/auth.py

    problem: "App has no authentication layer; user identity is only a session cookie UUID"

    root_cause: "Auth was never integrated — user_id is a random per-browser-session value, not a real account"

    required_fix: >
      Integrate a managed auth provider (Auth0, Clerk, or Supabase Auth).
      Inject a stable authenticated user_id into all callbacks.
      Configure secure cookies: Secure=true, HttpOnly=true, SameSite=Lax|Strict.

    constraints:
      - allowed_providers: Auth0 | Clerk | Supabase Auth only

    acceptance_criteria:
      - Every callback receives a stable, authenticated user_id
      - Session cookies meet the secure_cookie_config requirements

    status: "✅ IMPLEMENTED"
    
    implementation_notes: >
      - Created codes/auth.py with support for Auth0, Clerk, and Supabase Auth
      - Integrated with app.py: authentication initialized on startup
      - Replaced _session_id() with _get_user_id() across all callbacks (11 callbacks)
      - Secure cookies configured: Secure=true, HttpOnly=true, SameSite=Lax
      - Token caching implemented for performance (1-hour TTL)
      - Backward compatible: falls back to session UUIDs in local dev mode
      - See AUTHENTICATION_SETUP.md for complete configuration guide

    risk_if_not_fixed: HIGH


  ISSUE_009[x]:

    title: "No billing/subscription enforcement"
    category: billing

    files:
      - codes/app.py
      - codes/billing.py

    problem: "No payment or tier enforcement exists"

    root_cause: "Billing integration not yet built"

    required_fix: >
      Integrate Stripe Checkout + Customer Portal.
      Enforce tier gating (free: screener_only; paid: analyze_stock, live_metrics)
      at the callback level.

    constraints:
      - No custom billing logic allowed — Stripe only

    status: "✅ IMPLEMENTED"

    implementation_notes: >
      - Added `codes/billing.py` with Stripe + dev-fallback helpers and a
        lightweight `/billing/mark_paid` dev endpoint.
      - Initialized billing in `codes/app.py` and gated `run_analysis()`
        to require a paid subscription before running `analyze_stock()`.
      - Returns an upgrade URL (Stripe Checkout when configured, otherwise
        the dev `/billing/mark_paid` flow) when unpaid.

    risk_if_not_fixed: HIGH

    acceptance_criteria:
      - Free-tier users cannot invoke paid-tier callbacks
      - Checkout and Customer Portal flows work end-to-end

    risk_if_not_fixed: HIGH


  # ----------------------------
  # SECURITY
  # ----------------------------

  ISSUE_010:

    title: "Missing input validation, rate limiting, and safe error handling"
    category: security

    files:
      - codes/app.py

    problem: >
      No validation on ticker/portfolio_name/shares inputs; no rate limiting
      on expensive callbacks; raw exceptions/secrets may reach the UI or logs.

    root_cause: "Security hardening was deferred during single-user local development"

    required_fix: >
      - Validate ticker against ^[A-Z]{1,6}$
      - Validate portfolio_name (max 32 chars, alphanumeric + underscore)
      - Validate shares (min 5, max 1,000,000)
      - Add Flask-Limiter rate limiting to analyze_stock, load_universe,
        and simulation callbacks
      - Ensure logs and UI responses never expose secrets or raw exceptions

    constraints:
      - No behavior change for valid inputs

    acceptance_criteria:
      - Invalid ticker/portfolio_name/shares inputs are rejected with a safe message
      - Rate-limited endpoints return backoff/retry messaging, not raw errors
      - No API keys or stack traces appear in logs or UI

    risk_if_not_fixed: HIGH


  # ----------------------------
  # INFRASTRUCTURE
  # ----------------------------

  ISSUE_011:

    title: "App not configured for production deployment"
    category: infra

    files:
      - codes/app.py

    problem: "App runs via Dash dev server with debug=True; no reverse proxy, TLS, or edge protection configured"

    root_cause: "Infra setup was never done — local dev config only"

    required_fix: >
      - Serve via gunicorn or waitress with debug=false
      - Put nginx or platform proxy in front
      - Enforce TLS via Let's Encrypt or managed SSL
      - Put Cloudflare in front with WAF and rate limiting enabled
      - Store all secrets as environment variables only

    constraints:
      - No app logic changes required

    acceptance_criteria:
      - Production runs under gunicorn/waitress with debug disabled
      - TLS enforced end-to-end
      - Cloudflare WAF + rate limiting active

    risk_if_not_fixed: HIGH


  # ----------------------------
  # API STRATEGY
  # ----------------------------

  ISSUE_012:

    title: "API key and rate-limit handling not production-ready"
    category: api

    files:
      - codes/data/api_fetcher.py

    problem: >
      Rate-limit errors currently propagate as raw RateLimitError messages;
      no enforced caching guarantee of 1 call/ticker/day; no BYOK policy defined.

    root_cause: "Built for single-user local use; not yet hardened for shared multi-user API budgets"

    required_fix: >
      - Enforce server-owned keys only (no BYOK)
      - Guarantee price history caching at 1 API call per ticker per trading
        day, shared across all users
      - Replace raw RateLimitError surfacing with a retry/backoff message or
        queued request
      - Enforce tiering: free = screener_only, paid = analyze_stock + live_metrics

    constraints:
      - No behavior change to existing public function signatures

    acceptance_criteria:
      - No raw RateLimitError text reaches the UI
      - Verified shared cache prevents duplicate same-day fetches across users

    risk_if_not_fixed: HIGH


  # ----------------------------
  # LEGAL
  # ----------------------------

  ISSUE_013:

    title: "Missing required legal pages and disclaimers"
    category: legal

    files:
      - codes/app.py

    problem: "No Terms of Service, Privacy Policy, or required disclaimers exist"

    root_cause: "Legal pages were never drafted/added"

    required_fix: >
      Add Terms of Service and Privacy Policy pages.
      Add "Not financial advice" and refund/cancellation policy disclaimers.

    constraints:
      - Must be accessible pre-signup

    acceptance_criteria:
      - ToS and Privacy Policy pages are live and linked
      - Disclaimers are visible in the app

    risk_if_not_fixed: HIGH


# ================================
# SECTION B — CONTINUOUS (START AT LAUNCH, NEVER END)
# ================================

continuous_operations:

  dependency_scanning:
    tool: pip-audit | dependabot
    frequency: CI

  error_monitoring:
    tool: Sentry
    integration: app.py logging callback

  abuse_monitoring:
    signals:
      - scraping patterns
      - credential stuffing
      - API spikes

  incident_response:
    required: true
    includes:
      - key rotation procedure
      - rollback procedure
      - on-call ownership

  dependency_updates:
    cadence: regular

  access_review:
    cadence: periodic


# ================================
# EXECUTION ORDER (DEPENDENCY GRAPH)
# ================================

execution_order:

  1:
    - ISSUE_004
    - ISSUE_005
    - ISSUE_006
    - ISSUE_014

  2:
    - ISSUE_008
    - ISSUE_009

  3:
    - ISSUE_007

  4:
    - ISSUE_010

  5:
    - ISSUE_011

  6:
    - ISSUE_012

  7:
    - ISSUE_013

  8:
    - continuous_operations


# ================================
# GLOBAL RULES (HARD CONSTRAINTS)
# ================================

global_rules:

  blocking:
    must_be_complete_before_launch: true
    no_v1_v2_deferrals: true

  continuous:
    must_start_at_launch: true
    never_complete: true