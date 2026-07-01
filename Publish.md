pre_launch_readiness: intrinsic_iq

global_definition:
  purpose: >
    This document defines launch-blocking and continuous operational requirements.
  categories:
    BLOCKING: "Must be 100% complete before production launch"
    CONTINUOUS: "Must be active from launch onward and never considered complete"
  rule:
    - No BLOCKING item can be deferred to V1/V2
    - CONTINUOUS items must start at launch

execution_format:
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

section_a_blocking:

  ISSUE_004:
    title: Screener state is globally shared across users
    category: data-isolation
    files:
      - codes/engine/screener.py
    problem: "_progress is module-level global shared across all users"
    root_cause: "No per-user session isolation for progress tracking"
    required_fix: >
      Introduce per-user progress state store.
      Keep load_universe_background() as shared singleton job.
      Only UI progress must be per-user.
    constraints:
      - Universe fetch must remain global/shared
    acceptance_criteria:
      - Two users never see each other's progress
      - No polling cross-interference
    risk_if_not_fixed: high

  ISSUE_005:
    title: Portfolio data has no ownership boundary
    category: data-isolation
    files:
      - codes/portfolio.py
    problem: "Portfolio CRUD is keyed only by name"
    root_cause: "Missing user_id scoping in storage layer"
    required_fix: >
      Add user_id to all portfolio operations and cache keys.
      Example: p_{name} → {user_id}_p_{name}
    constraints:
      - list_portfolios returns only user-owned data
    acceptance_criteria:
      - User cannot access other users' portfolios
    risk_if_not_fixed: high

  ISSUE_006:
    title: App-level cache leaks cross-user state
    category: data-isolation
    files:
      - codes/app.py
    problem: "_portfolio_cache may mix user data across sessions"
    root_cause: "Shared in-memory global cache"
    required_fix: >
      Scope all sensitive caches by user_id.
      Validate whether analysis cache can remain global.
    constraints:
      - analysis cache may remain global if deterministic
    acceptance_criteria:
      - No incorrect ownership badges
      - No cross-user cache leakage
    risk_if_not_fixed: high

  ISSUE_007:
    title: SQLite not safe for concurrent multi-user writes
    category: db
    files:
      - codes/data/db.py
    problem: "SQLite single-writer model breaks under concurrency"
    root_cause: "No connection pooling or server-grade DB"
    required_fix: >
      Migrate to Postgres with connection pooling.
      Preserve DB API:
        init_db, upsert, get, get_all, delete, count
    constraints:
      - No app-level logic changes allowed
      - Preserve schema and whitelist safeguards
    acceptance_criteria:
      - No lock errors under concurrent usage
      - Full migration from existing DB
    risk_if_not_fixed: high

auth_and_billing:
  authentication:
    requirement: managed_auth_only
    allowed_providers:
      - Auth0
      - Clerk
      - Supabase Auth
    requirements:
      - stable user_id injected into all callbacks
      - secure cookies:
          Secure: true
          HttpOnly: true
          SameSite: Lax|Strict

  billing:
    provider: Stripe
    components:
      - Checkout
      - Customer Portal
    rules:
      - No custom billing system
      - Enforce tier gating at callback level

security_requirements:
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
    rule: "No secrets or raw exceptions exposed to users"

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

infrastructure:
  production:
    server: gunicorn | waitress
    debug: false

  proxy:
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

api_strategy:
  model: server_owned_keys_only
  rules:
    - no_byok: true

  caching:
    price_history:
      rule: "1 call per ticker per trading day globally"
      shared_across_users: true

  rate_limit_handling:
    behavior:
      - never expose RateLimitError
      - return retry message or queue request

  tiering:
    free:
      allowed: [screener_only]
    paid:
      allowed: [analyze_stock, live_metrics]

legal:
  required_pages:
    - Terms of Service
    - Privacy Policy
  disclaimers:
    - Not financial advice
    - Refund/cancellation policy required

section_b_continuous:

  dependency_scanning:
    tool: pip-audit | dependabot
    frequency: CI

  error_monitoring:
    tool: Sentry
    integration: app.py logging callback

  abuse_monitoring:
    signals:
      - scraping
      - credential stuffing
      - API spikes

  incident_response:
    required: true
    includes:
      - key rotation plan
      - rollback plan
      - on_call ownership

  dependency_updates:
    cadence: regular

  access_review:
    cadence: periodic

execution_order:
  1:
    - ISSUE_004
    - ISSUE_005
    - ISSUE_006
  2:
    - authentication_and_billing
  3:
    - ISSUE_007
  4:
    - security_requirements
  5:
    - infrastructure
  6:
    - edge_protection
  7:
    - api_rate_limiting_and_ux_handling
  8:
    - billing_enforcement
  9:
    - legal
  10:
    - section_b_continuous

global_rule:
  blocking:
    must_be_complete_before_launch: true
    no_v1_v2_deferral: true
  continuous:
    must_start_at_launch: true
    never_complete: true