# ================================
# PRE-LAUNCH READINESS — Factor Research (AI-Optimized Spec)
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



  # ----------------------------
  # DATABASE
  # ----------------------------

  


  # ----------------------------
  # AUTHENTICATION & BILLING
  # ----------------------------

  


  # ----------------------------
  # SECURITY
  # ----------------------------

  I


  # ----------------------------
  # INFRASTRUCTURE
  # ----------------------------

  


  # ----------------------------
  # API STRATEGY
  # ----------------------------

  

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

  ISSUE_026_ANALYTICS_OPERATIONS:
    status: active_at_launch
    category: analytics
    purpose: >
      Production operation, validation, and expansion plan for the analytics
      platform implemented in ISSUE_026.

    already_implemented:
      - async best-effort analytics event writes
      - analytics_events canonical event log
      - event query helpers for recent events, event counts, and top metadata values
      - product flow instrumentation for analysis, screener, factor lab, portfolio, pricing, and subscription events
      - runtime, cache-hit, and failure-class metadata on analysis/backtest events
      - session-level analytics opt-out endpoint at /privacy/analytics
      - privacy page toggle for session-level analytics opt-out
      - PostHog client identify/opt-in-opt-out sync via /privacy/analytics context
      - Sentry browser user-context sync via /privacy/analytics context

    launch_blockers: []

    launch_day_configuration:
      required_env:
        - POSTHOG_KEY (optional, only if PostHog is being used)
        - POSTHOG_HOST (optional, defaults to https://app.posthog.com)
        - MICROSOFT_CLARITY_ID (optional, only if Clarity is being used)
        - SENTRY_DSN (optional, only if browser Sentry is being used)
        - DATABASE_ANALYTICS_URL (recommended if analytics data should be isolated from market/app data)
      steps:
        - set the analytics provider environment variables in the production deployment target
        - deploy once with those values present
        - confirm the page head contains the expected provider snippets in production HTML
        - confirm /privacy renders the analytics preference toggle
        - confirm GET /privacy/analytics returns JSON for an active browser session

    production_validation:
      posthog:
        why: >
          Confirms real event delivery, opt-out behavior, and authenticated user identification.
        steps:
          - set POSTHOG_KEY and POSTHOG_HOST in production
          - deploy the app
          - open the app in a fresh browser session
          - visit /pricing, run an analysis, and run a Factor Lab backtest
          - verify the matching events arrive in PostHog
          - sign in and confirm events are associated with the authenticated user id
          - open /privacy and disable analytics for the session
          - repeat a tracked action and confirm no new client-side captures are emitted after opt-out
        success_criteria:
          - pricing_page_viewed, analysis_started, analysis_completed, backtest_started, and backtest_completed appear in PostHog
          - authenticated sessions are identified with the expected user id
          - opt-out suppresses further client-side tracking for the opted-out session

      clarity:
        why: >
          Confirms the Clarity script loads and that session recording behavior matches privacy expectations.
        steps:
          - set MICROSOFT_CLARITY_ID in production
          - deploy the app
          - load the site and verify the Clarity tag is present
          - navigate through a normal session and confirm the session appears in Clarity
          - verify privacy/legal language reflects actual Clarity usage before public rollout
        success_criteria:
          - Clarity receives production sessions
          - deployed privacy language matches actual tracking behavior

      sentry:
        why: >
          Confirms browser-side error capture and authenticated user context wiring.
        steps:
          - set SENTRY_DSN in production
          - deploy the app
          - load the site in an authenticated browser session
          - trigger a controlled browser-side test error from devtools
          - verify the event appears in Sentry
          - verify the Sentry event includes the authenticated user id when signed in
          - open /privacy, opt out, refresh, and verify Sentry clears browser user context for that session
        success_criteria:
          - browser-side errors arrive in Sentry
          - authenticated sessions include user context
          - opted-out sessions do not retain browser user context

    reporting_follow_up:
      objective: >
        Build first-class internal views on top of analytics_events before adding more tables.
      recommended_first_report:
        source: analytics_events
        views:
          - top viewed stocks from stock_viewed metadata.symbol
          - analysis completion/failure counts from analysis_completed and analysis_failed
          - cache hit ratio from analysis_completed/backtest_completed metadata.cache_hit
          - average runtime from analysis_completed/backtest_completed metadata.duration_ms
          - most used algorithms from algorithm_selected metadata.algorithm
          - screener usage from screener_run and screener_filter_changed
          - pricing funnel from pricing_page_viewed, subscription_started, subscription_completed
      implementation_note: >
        Start with read queries against analytics_events. Only add dedicated
        summary tables after real query volume or dashboard latency justifies it.

    future_schema_expansion:
      only_if_needed:
        - analytics_company_views
        - analytics_analysis_runs
        - analytics_portfolios
        - analytics_searches
        - analytics_subscriptions
        - analytics_performance
        - analytics_errors
      decision_rule: >
        Keep the single event log unless reporting queries become too expensive,
        too repetitive, or need stronger dimensional guarantees.

    deferred_feature_hooks:
      watchlist_event:
        current_state: not_applicable
        trigger: only if a watchlist feature is introduced later
        required_event: watchlist_added

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
