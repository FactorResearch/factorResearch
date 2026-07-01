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

  ISSUE_004:

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


  ISSUE_005:

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


  ISSUE_006:

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


  # ----------------------------
  # DATABASE
  # ----------------------------

  ISSUE_007:

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


# ================================
# AUTHENTICATION & BILLING (BLOCKING)
# ================================

auth_and_billing:

  authentication:

    provider: managed_auth_only

    allowed_providers:
      - Auth0
      - Clerk
      - Supabase Auth

    requirements:
      - stable user_id injected into all callbacks

      - secure_cookie_config:
          Secure: true
          HttpOnly: true
          SameSite: Lax|Strict


  billing:

    provider: Stripe

    components:
      - Checkout
      - Customer Portal

    rules:
      - No custom billing logic allowed
      - Tier enforcement must occur at callback level


# ================================
# SECURITY REQUIREMENTS (BLOCKING)
# ================================

security:

  validation:

    ticker:
      regex: "^[A-Z]{1,6}$"

    portfolio_name:
      max_length: 32
      allowed_chars: "alphanumeric + underscore"

    shares:
      min: 5
      max: 1000000


  logging:
    rule: "Never expose secrets or raw exceptions to users"


  rate_limiting:
    framework: Flask-Limiter

    applies_to:
      - analyze_stock
      - load_universe
      - simulation_callbacks


  api_key_handling:
    rules:
      - Never expose API keys in logs or responses
      - Never return raw exceptions to UI


# ================================
# INFRASTRUCTURE (BLOCKING)
# ================================

infrastructure:

  production:

    server: gunicorn | waitress
    debug: false


  reverse_proxy:

    required: nginx | platform_proxy


  tls:

    required: true
    method: lets_encrypt | managed_ssl


  edge_protection:

    provider: Cloudflare

    features:
      - WAF enabled
      - rate limiting enabled


  secrets:

    storage: environment_variables_only


# ================================
# API STRATEGY (BLOCKING)
# ================================

api_strategy:

  model: server_owned_keys_only

  no_byok: true


  caching:

    price_history:

      rule: "1 API call per ticker per trading day globally"
      shared_across_users: true


  rate_limit_handling:

    behavior:
      - Never expose raw RateLimitError
      - Return retry/backoff message OR queue request


  tiering:

    free:
      allowed:
        - screener_only

    paid:
      allowed:
        - analyze_stock
        - live_metrics


# ================================
# LEGAL (BLOCKING)
# ================================

legal:

  required_pages:
    - Terms of Service
    - Privacy Policy

  disclaimers:
    - Not financial advice
    - Refund/cancellation policy required


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

  2:
    - auth_and_billing

  3:
    - ISSUE_007

  4:
    - security

  5:
    - infrastructure

  6:
    - api_strategy

  7:
    - legal

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