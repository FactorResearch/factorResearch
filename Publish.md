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