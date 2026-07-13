# CLAUDE CODE ISSUE RUNNER

This system allows deterministic execution of known issues with minimal token usage.

---

# USAGE FORMAT

```
run ISSUE-XXX
```

---

# EXECUTION RULES (MANDATORY)



## Step 1 — Load Context

- Read **only**: `KNOWN_ISSUES.md`, `AI_CONTEXT.md`
- Extract: issue definition, file scope, acceptance criteria
- Never scan repository

---

## Step 2 — Scope Lock
- Work **only** on files explicitly listed in the issue
- If file missing/unclear → STOP and ask
---

## 3. Diagnosis (Very Brief)**
   - Think: root cause + exact location
   - Output **only**:
    - DIAGNOSIS: [one sentence root cause + function]
    - PLAN: [minimal fix description]
---

## Step 4 — Implementation Mode

- Apply **smallest possible patch**
- No refactor, rename, or unrelated changes
- Preserve APIs

---

## Step 5 — Tests

- Add/update minimal test only for this issue

---

## Step 6 — Output Format

- no need just push to git,if git not working show diff

---

# GLOBAL CONSTRAINTS

Never:

* scan full repo
* fix multiple issues in one run
* rewrite modules
* “improve architecture”
* optimize unrelated code

Always:

* minimal diff
* single issue focus
* deterministic output
* push to git after successful run
# FILE LOCK RULE:

If file is not explicitly listed in ISSUE → it is forbidden to open.
---

# ISSUE HANDLING MAP

## ISSUE TYPES

### Type A: Single-file bug

→ modify only one file

### Type B: Multi-file logic consistency

→ modify ONLY listed files

### Type C: Investigation required

→ stop after diagnosis

---

# EXAMPLE EXECUTION

User:

```
run ISSUE-003
```

Agent:

1. Reads ISSUE-003
2. Opens only <filefromissue>.py
3. Diagnoses covariance error
4. Applies fix
5. Adds test
6. push to git

---

# FAILURE RULE

If issue is ambiguous:

DO NOT GUESS.

Instead output:

```
NEED CLARIFICATION:
- missing definition of X
- unclear expected behavior of Y
```

Stop immediately.

---

# OPTIMIZATION GOAL

This system is designed to:

* reduce token usage by ~50–70%
* eliminate repo-wide scanning
* enforce deterministic patches
* improve test coverage reliability

# KNOWN_ISSUES.md

# Financial Model Issue System (Agent Optimized)

This file is the **single source of truth for all fixable defects**.

---

# Global Rules (MANDATORY)

When fixing any issue:

1. Load only:

   * KNOWN_ISSUES.md
   * AI_CONTEXT.md
   * PROJECT_MAP.md
   * explicitly selected files

2. Work on exactly ONE issue per run.

3. Do NOT scan the full repository.

4. Do NOT refactor unrelated code.

5. Output must be:

   * pushed to git
   * tests if required
   * no extra commentary unless asked

6. If a dependency outside allowed files is required → STOP and ask.

---

# ISSUE FORMAT STANDARD

Each issue must contain:

* Clear root cause
* Explicit file scope
* Deterministic fix
* Verifiable acceptance criteria

No vague instructions allowed.

---

# ACTIVE ISSUES

---

# ISSUE_001:
   
 Status:[x]
  title: "Sector dropdown is empty due to missing metadata layer (SEC facts not available at startup)"
  category: data-architecture

  files:
    - codes/engine/screener.py
    - codes/engine/universe.py
    - codes/api/filters.py
    - codes/frontend/static/js/*

  problem: >
    Sector (and other filter metadata) is derived from SEC facts that are only downloaded lazily
    during user-triggered analysis. As a result, at application startup the universe has no sector
    information, causing the sector dropdown to render empty and screener filters to be incomplete.

  root_cause: >
    Tight coupling between UI filter metadata (sector/industry) and lazy-loaded SEC facts.
    The frontend expects filter-ready metadata at startup, but backend only populates it during
    per-stock analysis, leaving initial dataset incomplete.

  current_behavior:
    - Universe loads at startup without sector/industry enrichment
    - SEC facts are fetched only when user clicks "analyze"
    - Dropdown population happens only once at initial load
    - No reactive refresh of filter state after SEC enrichment occurs

  required_fix: >
    Decouple UI filter metadata from SEC fact ingestion.

    Introduce a dedicated lightweight "company metadata layer" (sector, industry, exchange, country)
    that is loaded at startup independently of SEC analysis.

    Update screener initialization to:
      1. Load universe (symbols)
      2. Load metadata cache (precomputed or lightweight API)
      3. Build filter dropdowns from metadata layer only
      4. Keep SEC facts strictly for analysis/scoring only

    Optional enhancement:
      - Add periodic metadata refresh job (daily/weekly)
      - Persist metadata cache locally (Redis or JSON)

  constraints:
    - SEC facts remain lazy-loaded per user action (no full prefetch)
    - No full SEC dataset download at startup (performance constraint: must stay fast)
    - Universe loading remains global singleton
    - Metadata must be lightweight (< few MB total)

  acceptance_criteria:
    - Sector dropdown is populated immediately on page load
    - Industry filter also populated without requiring any analysis
    - Screener filters work for all stocks, not only analyzed ones
    - SEC analysis remains unchanged and still lazy-loaded
    - No increase in startup time (target: < 2–5 seconds total init)

  risk_if_not_fixed: HIGH

---

---
# ISSUE_002:
   
 Status:[x]
  title: complete postgress db migration
  category: data-architecture

  files:
    - codes/app.py
    - codes/data/db.py
    - codes/workers/sec_refresh_worler.py


  problem: >
    app is defaulting to sql lite, we need to use postgres sql, in our postgress sql, we have 4 db as follow 
    factorresearch_users,factorresearch_market,factorresearch_jobs,factorresearch_analytics.
    sec_refresh_worker muust save its tabels in market db

  root_cause: >
      wiring is not correct in db.pu

  current_behavior:
    - when python -m codes.workers.sec_refresh_worker is executed we save data to sql lite insted of postgress

  required_fix: >
    remove sql lite completly, no longer need it, move everything to postgres 


  constraints:


  acceptance_criteria:
    - we only use postgress, and save data into correct db
    
  risk_if_not_fixed: HIGH

---

---
# ISSUE_003:

  Status: [x]

  title: Build a validated Graham universe to eliminate unnecessary SEC downloads

  category: data-pipeline

  files:
    - codes/data/universe.py
    - codes/workers/sec_refresh_worker.py
    - codes/data/sec_data.py

  problem: >
    The current universe is generated directly from the SEC
    company_tickers.json file. This includes ETFs, mutual funds,
    trusts, SPACs, shell companies, and other non-operating entities.
    As a result, the SEC refresh worker downloads SEC Company Facts
    for many securities that will never qualify for Graham analysis,
    wasting time, bandwidth, storage, and processing.

  root_cause: >
    The universe builder has no concept of security type or eligibility.
    It treats every SEC reporting entity as a candidate for Graham
    analysis because filtering occurs only after financial data has
    already been downloaded.

  current_behavior:
    - Load every SEC ticker.
    - Download SEC Company Facts for every ticker.
    - Later reject funds and other non-operating entities during screening.

  required_fix: >
    Investigate building an "eligible Graham universe" before SEC data
    collection. Determine the most reliable source for identifying
    operating companies (e.g. FMP company profile metadata such as
    isEtf, isFund, security type, exchange, etc.). Cache the validated
    universe and have the SEC refresh worker process only eligible
    companies. Avoid heuristic filtering based on company names.

  constraints:
    - Do not rely on company name keywords such as "Fund", "Trust",
      or "ETF".
    - Minimize additional API usage.
    - The universe should be reproducible and refreshable on demand.
    - Preserve support for legitimate operating companies such as
      Berkshire Hathaway (BRK.B).

  acceptance_criteria:
    - SEC Company Facts are downloaded only for eligible operating companies.
    - ETFs, mutual funds, and other unsupported security types are
      excluded before SEC downloads begin.
    - The eligibility rules are centralized and easily extensible.
    - The universe can be refreshed independently of the SEC data cache.

  risk_if_not_fixed: MEDIUM

---
---
# ISSUE_004:

 Status:[~]

 title: implement seo optimized historical stock analysis pages

 category: product-growth / seo / data-architecture


files:
  - codes/app.py
  - codes/routes/analyze.py
  - codes/services/analysis_snapshot_service.py
  - codes/models/analysis_snapshot.py
  - codes/workers/daily_analysis_worker.py
  - codes/sitemap_generator.py


problem: >

  Current stock analysis results are generated dynamically and are not
  discoverable through search engines. Historical analysis results are not
  permanently stored, preventing users from viewing how a stock analysis
  changed over time.

  We need to create SEO-friendly public analysis pages with unique URLs while
  preserving user privacy for custom algorithms.

  Example:

  https://www.factorresearch.com/analyze/apple/20260301

  These pages will allow users to discover FactorResearch through search
  engines and create a proprietary historical investment analysis database.


solution: >

  Implement a historical analysis snapshot system that stores only
  FactorResearch default algorithm results.

  Each standard algorithm execution creates a permanent snapshot containing:

  - stock information
  - factor scores
  - valuation metrics
  - quality metrics
  - growth metrics
  - momentum metrics
  - risk metrics
  - market context
  - algorithm version

  Generate public SEO pages using:

  /analyze/{ticker}/{YYYYMMDD}

  Example:

  /analyze/AAPL/202060103



requirements:


  analysis_storage:

    create_analysis_types:

      - STANDARD
      - CUSTOM_USER
      - BACKTEST
      - EXPERIMENTAL


    storage_rules:

      STANDARD:
        status: store permanently
        public_url: yes
        seo_index: yes


      CUSTOM_USER:
        status: temporary only
        public_url: no
        seo_index: no


      BACKTEST:
        status: user specific
        public_url: no


      EXPERIMENTAL:
        status: internal only



  database_changes:


    create_table:

      analysis_snapshots:

        purpose: >

          Store historical snapshots of FactorResearch standard algorithm
          results for SEO pages and historical comparisons.


        columns:

          - id
          - ticker
          - company_name
          - analysis_date
          - algorithm_version
          - valuation_score
          - quality_score
          - growth_score
          - momentum_score
          - risk_score
          - final_rating
          - intrinsic_value
          - market_price
          - market_fear_score
          - created_at



      analysis_versions:

        purpose: >

          Track algorithm versions so historical analysis can be reproduced
          accurately.



seo_pages:


  url_structure:

    format:

      /analyze/{ticker}/{date}


    examples:

      - /analyze/AAPL/20260404
      - /analyze/MSFT/202060404
      - /analyze/NVDA/202060303



  page_content:

    include:

      - company name
      - analysis date
      - factor scores
      - valuation summary
      - quality metrics
      - growth metrics
      - risk metrics
      - final rating
      - algorithm version



  seo_metadata:

    generate:

      title:

        example:

          Apple Stock Analysis July 8 2026 | FactorResearch


      description:

        include:

          - valuation information
          - factor ranking
          - analysis date
          - investment metrics



historical_analysis:


  feature:

    view_previous_analysis:


      example:

        Apple Analysis History:

        2026-07-08
        Rating: BUY
        Score: 82


        2026-06-08
        Rating: HOLD
        Score: 74



  comparison:

    compare_dates:

      example:

        Compare:

        /analyze/AAPL/202060101

        vs

        /analyze/AAPL/20260303


      display_changes:

        - score changes
        - valuation changes
        - factor movement
        - rating changes



seo_growth:


  sitemap:


    create:

      /sitemap-analysis.xml


    include:

      - latest stock analyses
      - historical analysis pages



  internal_links:


    automatically_generate:

      - similar factor stocks
      - industry competitors
      - previous analysis dates
      - related market sectors



daily_pipeline:


  workflow:

    - market_close
    - refresh_market_data
    - run_standard_factor_algorithm
    - save_analysis_snapshot
    - publish_analysis_page
    - update_sitemap



implementation_phases:


  phase_1_core:[x]


    estimated_time: 1-2 weeks


    tasks:

      - create analysis snapshot database
      - store standard algorithm results
      - create analyze URL route
      - display historical analysis pages
      - generate sitemap



  phase_2_seo_expansion:[x]


    estimated_time: 2-4 weeks


    tasks:

      - improve metadata generation
      - add structured data
      - create internal linking system
      - optimize page indexing



  phase_3_data_moat:[can't be completed until we launch, takes 4 months]


    estimated_time: 1-3 months


    tasks:

      - daily historical snapshots
      - expand to global markets
      - track long-term factor changes
      - build historical investment database



expected_result: >

  FactorResearch becomes a searchable historical investment analysis platform.

  Users can search:

  - "Apple stock analysis July 2026"
  - "Tesla valuation history"
  - "Microsoft factor score"

  and discover FactorResearch pages.

  Over time the platform builds a proprietary dataset:

  - millions of historical stock analyses
  - factor score history
  - valuation history
  - algorithm version history
  - market condition history

  This creates an SEO acquisition engine and a long-term competitive moat.

---
---
# ISSUE_005:

Status: [x]

title: “Implement shared factor engine with user-customizable weighting and strategy cache”

category: architecture

files:

* codes/engine/factor_engine.py
* codes/engine/scoring.py
* codes/engine/backtest.py
* codes/data/db.py
* codes/models.py
* codes/routes/analysis.py
* codes/routes/backtest.py

problem: >
The current analysis architecture assumes a single scoring model. The
platform roadmap allows every user to customize the weighting of
Graham, Buffett, Quality, Financial Health, Growth, Momentum, and
future factors, while keeping the underlying company analysis shared.
Recomputing complete analysis for every user would not scale and would
duplicate identical computations.

root_cause: >
Company analysis, factor computation, weighted scoring, and backtesting
are currently treated as a single pipeline rather than independent
layers.

required_fix: >
Refactor the scoring architecture into independent layers:

Layer 1:
Shared factor engine.

Compute atomic factor scores (Graham, Buffett, Quality, Financial
Health, Growth, Momentum, etc.) once per company whenever market data
or financial statements change.

Layer 2:
Shared company analysis.

Narrative analysis should reference the shared factor scores instead
of embedding user-specific weighting.

Layer 3:
User weighting.

Store only user weight configurations. Never duplicate company
analysis or factor scores for each user.
Overall score should be computed dynamically from:
  weighted_score =
    Σ(factor_score × user_weight)
This calculation should occur at request time and should not require
regenerating analysis.

Layer 4:
Strategy cache.

Normalize every user weighting configuration and generate a stable
strategy hash.
Example:
  Graham=50
  Buffett=0
  Quality=30
  Health=20
  ↓
  strategy_hash
Identical weighting configurations from different users should reuse
the same cached backtest results.

Layer 5:
Historical factor snapshots.

Store factor scores by company and historical rebalance date so
backtests only recompute weighted rankings rather than recalculating
every financial metric.

requirements:

* Separate factor calculation from weighted scoring.
* Company factor scores must be shared globally.
* User profiles store only weighting preferences.
* Company analysis must remain identical for all users unless explicitly
    personalized.
* Weighted scores must update instantly when weights change.
* Backtests must use historical factor snapshots instead of rebuilding
    all factor metrics.
* Introduce strategy hashing to maximize cache reuse across users.
* Cache keys should include:
    * strategy_hash
    * data_version
    * rebalance_frequency
    * investment_universe
    * start_date
    * end_date
* Automatically invalidate cached strategies when historical factor
    data changes.

acceptance_criteria:

* Changing user weights updates rankings without regenerating company
    analysis.
* Two users with identical weights produce identical scores and share
    the same cached backtest.
* Company factor scores exist only once in storage.
* Historical backtests reuse stored factor snapshots.
* Strategy hashing eliminates duplicate backtest computation.
* Architecture supports adding new factors without redesigning the
    scoring engine.

priority: High
# ISSUE_006:

Status: [x]

title: "Add Market Fear Gauge (VIX/VIXEQ Regime Analysis)"
category: market-intelligence

files:

- codes/engine/market_fear.py
- codes/engine/analysis.py
- codes/data/market_data.py
- codes/ui/analysis_badges.py
- codes/templates/analysis.html

problem: >
Every stock analysis is currently performed in isolation from the overall
market environment. Intrinsic value answers whether a stock is cheap or
expensive, but it does not communicate whether current market conditions
suggest investors are complacent, cautious, or fearful.

As a result, users receive a valuation without understanding whether the
current environment is one where opportunities are likely increasing or
where market optimism may still be suppressing future returns.

goal: >
Introduce a Market Fear Gauge that combines VIX and VIXEQ into a simple,
easy-to-understand macro indicator shown on every stock analysis.

The gauge should NEVER influence valuation calculations or stock scores.

It is purely contextual information that helps users interpret whether the
current market environment is generally favorable for value investing.

background: >
VIX measures implied volatility using capitalization-weighted S&P 500
options.

VIXEQ measures implied volatility using equal-weight S&P 500 options.

Because VIXEQ gives equal importance to every company, it is often a better
measure of stress across the average stock.

When VIXEQ rises significantly above VIX, market fear is broadening beyond
mega-cap companies, which historically tends to coincide with improving
opportunities for long-term value investors.

important_principle: >
Market fear is NOT a prediction of a crash.

The indicator must never claim that a decline is imminent.

Instead it communicates:

"How favorable is the current market environment for finding future value
opportunities?"

calculation:

fetch:
- current VIX
- current VIXEQ

compute:

```
spread =
  VIXEQ - VIX

ratio =
  VIXEQ / VIX

optional:
  rolling_252_day_mean(spread)

optional:
  rolling_252_day_std(spread)

optional:
  z_score =
  (spread - mean) / std
```

preferred_signal: >
Use the standardized spread (Z-score) whenever historical data is available.

If insufficient history exists, fall back to the raw spread and ratio.

market_regimes:

VERY_LOW_FEAR:

```
conditions:
  - VIX low
  - spread near zero

badge:
  "Low Market Fear"

color:
  Green

interpretation:
  Market participants are generally optimistic.

  High-quality businesses may continue performing well, but broad
  undervaluation is less common.

  Continue demanding a strong margin of safety.
```

NORMAL:

```
badge:
  "Normal Market Conditions"

color:
  Blue

interpretation:
  Market sentiment is balanced.

  Continue evaluating businesses solely on intrinsic value.
```

ELEVATED:

```
badge:
  "Elevated Market Fear"

color:
  Amber

interpretation:
  Investors are becoming increasingly defensive.

  Volatility may create additional buying opportunities if prices fall
  faster than intrinsic value.

  Consider monitoring watchlists closely.
```

HIGH:

```
badge:
  "High Market Fear"

color:
  Orange

interpretation:
  Fear is spreading across the broader market.

  Many businesses may begin trading closer to or below intrinsic value.

  This environment deserves increased research activity.
```

EXTREME:

```
badge:
  "Extreme Market Fear"

color:
  Red

interpretation:
  Market stress is unusually high.

  Historically these periods have often produced exceptional long-term
  buying opportunities for financially strong businesses.

  Increased caution is still required because some companies may be facing
  genuine deterioration rather than temporary price declines.
```

analysis_integration:

Every stock analysis should include a small Market Fear section.

Example:

---

Market Fear Gauge

Badge:
🟠 Elevated Market Fear

Current Reading

VIX:
22.4

VIXEQ:
27.1

Spread:
+4.7

Interpretation

Market volatility is expanding beyond large-cap companies.

Historically this type of environment tends to increase the number of
potential value opportunities.

IntrinsicIQ still evaluates this company independently of market sentiment,
but continued market weakness could improve future entry prices.

---

important_rules:

- Never modify intrinsic value calculations.
- Never alter Graham Score.
- Never alter Buffett Score.
- Never alter Quality Score.
- Never alter ranking engine.
- Never alter portfolio optimizer.

This feature is informational only.

future_extensions:

- Historical Market Fear chart.
- Fear regime timeline.
- Fear indicator on screener.
- Watchlist notifications when fear enters High or Extreme.
- Portfolio dashboard showing current market regime.
- Backtest performance by fear regime.
- Overlay Market Fear on historical buy recommendations.
- Optional macro score combining:
    - VIX
    - VIXEQ
    - Credit spreads
    - Yield curve
    - Market breadth
    - High Yield OAS
    - Advance/Decline line

  expected_benefit: >
  This feature gives users valuable macro context without compromising the
  philosophy of IntrinsicIQ.

  It reinforces that intrinsic value remains the primary investment decision,
  while market fear simply helps explain whether the current environment is
  likely producing more or fewer valuation opportunities.

  The feature aligns naturally with Benjamin Graham's and Warren Buffett's
  philosophy of taking advantage of market pessimism rather than reacting to
  it emotionally.
  notes: >
  This refactor establishes the long-term scoring architecture for
  Factor Research Company fundamentals become the shared source of truth,
  while personalization is achieved by applying lightweight user-defined
  weightings over shared factor scores. This minimizes storage,
  maximizes cache efficiency, and enables scalable customization as the
  platform grows.
---
# ISSUE_007:

Status: [x]

title: "Phase E alternative data framework"

category: data

files:

* codes/models/alternative_data.py
* codes/data/sec_data.py
* codes/data/db.py
* codes/app.py
* tests/test_alternative_data.py
* tests/test_sec_8k_filings.py
* tests/test_phase_e_provider_fetchers.py
* SCORING_METHODOLOGY.md

problem: >
Alternative data was previously represented as a generic placeholder. The
platform needs an explicit Phase E scope that separates deterministic,
auditable signals available today from provider-dependent research areas.

required_fix: >
Add Phase E Alternative Data coverage for:

- [x] SEC 8-K sentiment analysis (deterministic, auditable, no external AI dependency)
- [x] Hiring velocity via job posting trends
- [x] Web traffic analytics (once a reliable long-term data source is available)
- [x] Insider buying and selling trends
- [x] Institutional ownership changes
- [x] Patent and intellectual property activity
- [x] Supply chain relationship analysis (long-term research)

completion_notes: >
Phase E is complete at the signal-framework level. SEC 8-K sentiment,
insider buying/selling trends, institutional ownership changes, and patent/IP
activity are wired to current data sources. Hiring velocity, web traffic, and
supply-chain relationship analysis expose deterministic trend-scoring hooks
and remain neutral until durable provider data is supplied.

important_rules:

- Alternative Data remains display-only until durable provider-backed coverage exists.
- Never alter Graham Score.
- Never alter Buffett Score.
- Never alter Quality Score.
- Never alter the enhanced composite score.
- SEC 8-K sentiment must stay deterministic and auditable.

---
# ISSUE_008
Status: [x]
**Objective:**

Implement a subscription-based pricing model where users receive limited access to experience IntrinsicIQ analysis, then require payment to unlock unlimited research capabilities and advanced quantitative features.

The pricing model should differentiate between:

- Low-cost cached analysis features
- User customization features
- High-compute research features (backtesting, optimization, simulations)

**User Access Model**

**Trial User**

**Purpose:**

Allow users to experience the platform value before requiring payment.

Limits:

- ✅ Maximum 3 company analyses
- ✅ View full company analysis
- ✅ View Graham/Buffett/Quality scores
- ✅ Adjust custom factor weights
- ✅ Preview personalized composite score
- ❌ No historical backtesting
- ❌ No saved strategies
- ❌ No portfolio analytics
- ❌ No unlimited screening

After the third analysis:

Display upgrade prompt:

You have used your 3 free analyses.

Unlock IntrinsicIQ Premium:

✓ Unlimited company analysis

✓ Custom investment strategies

✓ Historical backtesting

✓ Portfolio analytics

✓ Strategy tracking

**Premium Features**

**Unlimited Analysis**

Unlock:

- Unlimited company research
- Unlimited factor scoring
- Unlimited custom weighting
- Full screening capabilities

Implementation:

Add user entitlement check before analysis execution.

Example:

request analysis

|

▼

check subscription status

trial_remaining > 0

|

▼

allow analysis

decrement counter

OR

premium_user

|

▼

allow unlimited access

**Custom Factor Weighting**

**Status: Existing functionality**

Allow all trial users to experiment with custom formulas.

Example:

Default:

Graham       25%

Buffett      25%

Quality      20%

Health       15%

Growth       10%

Momentum      5%

User customization:

Graham       50%

Buffett       0%

Quality      30%

Health       20%

Growth        0%

Momentum      0%

The personalized score calculation remains available during trial.

Purpose:

Increase user engagement and demonstrate value.

**Backtest Engine Premium Gate**

**Highest-value premium feature**

Backtesting requires subscription.

Before execution:

User clicks "Run Backtest"

|

▼

check subscription

premium?

|

├── Yes

│      Run backtest

│

└── No

Show upgrade prompt

**Backtest Entitlement Levels**

**Premium**

Includes:

- Custom weight backtesting
- Historical performance
- CAGR
- Sharpe
- Maximum drawdown
- Strategy comparison

**Professional (Future)**

Includes:

- Large universe backtesting
- Daily rebalance
- Factor optimization
- Monte Carlo simulation
- API access
- Export research data

**Required Database Changes**

**User Subscription Table**

New table:

subscriptions

id

user_id

plan

status

start_date

end_date

stripe_customer_id

stripe_subscription_id

Plans:

trial

premium

professional

cancelled

**User Usage Tracking**

New table:

user_usage

user_id

analysis_count

period_start

period_end

feature_usage

Track:

company_analysis

screening_runs

backtests

portfolio_analysis

**Feature Permission Layer**

Create centralized permission service:

New file:

codes/services/permissions.py

Responsibilities:

can_access_feature(

user,

feature_name

)

Examples:

can_access_feature(

user,

"backtest"

)

returns:

True / False

Features:

ANALYSIS

CUSTOM_WEIGHTS

SCREENING

BACKTEST

PORTFOLIO_ANALYTICS

EXPORT

Avoid scattering subscription checks throughout the application.

**UI Changes**

Add:

UpgradeBanner

FeatureLockedModal

UsageCounter

Examples:

Trial:

2 / 3 free analyses remaining

Locked feature:

Historical backtesting requires Premium

Unlock strategy validation →

**Stripe Integration**

Files:

codes/payments/

stripe_client.py

subscriptions.py

webhooks.py

Implement:

- Checkout session creation
- Subscription status sync
- Cancellation handling
- Payment failure handling
- Webhook validation

**Analytics Tracking**

Track conversion funnel:

Events:

analysis_completed

custom_weight_created

backtest_clicked

upgrade_viewed

subscription_started

Important funnel:

Company Analysis

↓

Custom Strategy Created

↓

Backtest Attempted

↓

Subscription Conversion

**Acceptance Criteria**

- Trial users are limited to 3 company analyses.
- Trial usage persists across sessions.
- Premium users have unlimited analysis access.
- Custom weighting works for trial and premium users.
- Backtesting requires an active subscription.
- Feature restrictions are enforced server-side.
- Subscription status updates automatically from payment provider.
- Users receive clear upgrade prompts when hitting limits.
- Existing factor engine and backtest engine continue working without major refactoring.

**Future Enhancement**

Introduce usage-based premium tiers:

Premium:

Normal backtests

Professional:

Large universe research

Institutional:

API + bulk research

The architecture should support additional paid tiers without rewriting feature access logic.

**TEST RULE**: Add minimal test `test_issue_XXX_*.py` when needed.
---
# ISSUE_009:
Status: [fixed]
psycopg.OperationalError: connection failed: connection to server at "127.0.0.1", port 5432 failed: FATAL:  database "analysis_cache" does not exist

getting to analyze tab from screener works but opening the links on it is own does not http://127.0.0.1:8050/analyze/NVDA/20260709

risk_if_not_fixed: HIGH
---
# ISSUE_010:

 Status:[x]
  title: light mode and dark mode
  category: style

  files:
    - codes/app.py
    - assets


  problem: >
    app is currently only in dark mode


  required_fix: >
    - implement light mode, then allow users to switch between them, save user prefrences

  acceptance_criteria:
    - toggle to switch between each mode and save that into user profile

  risk_if_not_fixed: LOW
---
# ISSUE_011:

 Status:[x]
  title: analyze tab is too long
  category: style

  files:
    - codes/analyze.py
    - assets


  problem: >
    analyze tab is a large page that user have to scroll in one shot.

  required_fix: >
    - break the page into smaller section, each section is behind vertical carousel like section that allows people to get to.
      on the left side are dots showing how many pages exist, hovering over those dots expand and show title for each section.
      client can jump to each section by just clicking
    - here is proposed structure
      - the first slide shows, the company-header and composite banner
      - second slide Intrinsic Value Estimate,Economic Moat Rating Details
      - third slide Economic Moat Quality & Value,Momentum Analysis
      - fourth slide Risk & Performance — 10yr History , Risk Score Breakdown
      - fifth slide Moat Rating Analysis - Intrinsic Value Analysis
      - sixth slide financial health and z score
      - sevent slide, market regime and fcf quality
      - eight capital allocation and growth
      - nine slide alt data , factor momentum and opt signal
      - 10 remaning graph
      - add to portfolio should always be available in all slides

  acceptance_criteria:
    - smoth scrolling between slides, and functioning system in mobile and tablet.

  risk_if_not_fixed: LOW

---
# ISSUE_012:

 Status:[x]
  title: "Billing routes trust user_id from query string"
  category: security-authorization

  files:
    - codes/billing.py
    - codes/app_modules/session.py
    - codes/payments/stripe_client.py
    - tests/test_issue_012_billing_auth.py

  problem: >
    /billing/checkout and /billing/portal accept user_id from request query
    parameters before falling back to the session. A caller can request a
    checkout or billing portal URL for a different user_id if they know or
    guess it, causing subscription/customer metadata to be associated with the
    wrong account.

  root_cause: >
    codes/billing.py lines 24 and 37 use flask.request.args.get("user_id")
    as the authority for paid-account actions instead of deriving identity
    exclusively from the authenticated/session user boundary.

  required_fix: >
    Remove user_id query-string trust from production billing routes. Use
    get_user_id() or the authenticated session identity only, and reject
    missing/unauthenticated users. Keep development-only mark_paid safe by
    either using the current session user or gating explicit user_id behind a
    clearly local-only path.

  acceptance_criteria:
    - /billing/checkout ignores or rejects user_id query parameters.
    - /billing/portal ignores or rejects user_id query parameters.
    - Stripe checkout metadata and client_reference_id always match the
      current authenticated/session user.
    - Tests prove a request with ?user_id=other_user cannot create a checkout
      or portal for other_user.

  risk_if_not_fixed: HIGH

---
# ISSUE_013:

 Status:[x]
  title: "Auth0 callback reflects provider errors and exception details"
  category: security-information-disclosure

  files:
    - codes/auth.py
    - tests/test_issue_013_auth_errors.py

  problem: >
    The Auth0 callback route returns raw provider error values, token exchange
    response bodies, and exception messages to the browser. These responses can
    leak sensitive implementation details and can reflect untrusted input in an
    authentication page.

  root_cause: >
    codes/auth.py lines 345-376 return f-string responses containing
    request.args["error"], response.text, and caught exception text.

  required_fix: >
    Return generic user-facing authentication errors from the callback route,
    log sanitized details server-side, and avoid embedding provider response
    bodies or exception messages in HTTP responses.

  acceptance_criteria:
    - /callback?error=<script...> response does not contain raw supplied text.
    - Token exchange failures return a generic message.
    - Exception paths return a generic message in production and do not expose
      secrets or stack details.
    - Tests cover reflected error and token-exchange failure paths.

  risk_if_not_fixed: MEDIUM

---
# ISSUE_014:

 Status:[x]
  title: "Portfolio cache keys reject real auth IDs and portfolio names"
  category: correctness-security

  files:
    - codes/portfolio.py
    - codes/data/cache.py
    - tests/test_issue_014_portfolio_cache_keys.py

  problem: >
    Portfolio persistence builds cache keys from raw user_id and portfolio
    name. The cache layer correctly allows only [a-z0-9_.-], but real auth
    provider IDs often contain characters such as "|" and users may create
    portfolio names with spaces. Those keys raise ValueError in cache._path;
    cache.write swallows the error, so portfolio saves can appear to succeed
    while data is not persisted.

  root_cause: >
    codes/portfolio.py lines 98-124 interpolate raw user-controlled values
    into cache keys, while codes/data/cache.py lines 18-27 reject unsafe
    filename characters.

  required_fix: >
    Add a deterministic portfolio cache-key encoder for user_id and portfolio
    name, or migrate portfolio storage to the database. Preserve the displayed
    portfolio name inside the saved payload; only the storage key should be
    normalized. Surface write failures in tests instead of silently accepting
    lost data.

  acceptance_criteria:
    - create/load/delete works for auth IDs like "auth0|abc123".
    - create/load/delete works for portfolio names like "Long Term Value".
    - Existing safe keys remain readable or have a migration fallback.
    - Tests prove portfolio writes do not silently disappear on unsafe input.

  risk_if_not_fixed: HIGH

---
# ISSUE_015:

 Status:[x]
  title: "Security test suite is stale and currently cannot validate security module"
  category: security-testing

  files:
    - codes/security.py
    - tests/test_security.py
    - requirements.txt

  problem: >
    The security test suite references helpers that are not present in the
    current security module, including validate_ticker, validate_email,
    validate_numeric, validate_json_payload, RateLimiter,
    SensitiveDataEncryptor, and log_security_event. In this environment the
    targeted security tests also fail during collection because pandas is not
    installed, so the app currently lacks a passing security regression signal.

  root_cause: >
    tests/test_security.py appears to describe an older security API while
    codes/security.py now focuses on CSRF/header helpers. Dependency setup is
    also not guaranteed before test execution.

  required_fix: >
    Reconcile tests with the current security API or restore the missing
    helpers intentionally. Ensure the documented test command installs/uses
    requirements and can run in CI before security-sensitive changes merge.

  acceptance_criteria:
    - pytest tests/test_security.py collects and runs successfully.
    - Tests cover current CSRF, security-header, input-validation, and
      encryption behavior.
    - CI or local setup fails fast when dependencies like pandas are missing.

  risk_if_not_fixed: MEDIUM

---
# ISSUE_016:

 Status:[x]
  title: "Startup launches large SEC metadata backfill on every app process"
  category: performance-reliability

  files:
    - codes/app.py
    - codes/data/company_metadata.py
    - codes/engine/screener.py
    - tests/test_issue_016_metadata_backfill.py

  problem: >
    App startup calls company_metadata.start_background_refresh() with the full
    universe. The worker can issue up to 2,000 SEC submissions requests per
    process at roughly 3/sec. This is technically asynchronous, but it still
    competes for CPU, network, logs, SEC rate budget, and dyno/container
    resources immediately after every deploy/restart.

  root_cause: >
    codes/app.py line 199 starts the metadata backfill unconditionally, and
    codes/data/company_metadata.py lines 90-125 processes up to max_symbols
    missing entries in one daemon thread without a persisted cooldown or
    deployment-wide coordination.

  required_fix: >
    Move large metadata refreshes to an explicit worker/scheduled job or add a
    persisted cooldown and small startup budget. The web process should serve
    cached metadata instantly and only perform tiny opportunistic refreshes
    during request handling.

  acceptance_criteria:
    - Starting the web app does not trigger thousands of outbound SEC requests.
    - Metadata backfill has a persisted cooldown or runs only in a worker.
    - Screener remains usable immediately with cached/unknown sector values.
    - Tests prove startup does not call the large backfill path by default.

  risk_if_not_fixed: MEDIUM

---
# ISSUE_017:

 Status:[x]
  title: "Portfolio encryption fails open to plaintext when ENCRYPTION_KEY is missing or invalid"
  category: security-data-protection

  files:
    - codes/security.py
    - codes/data/cache.py
    - tests/test_issue_017_encryption_fail_closed.py

  problem: >
    Portfolio cache payloads are intended to be encrypted at rest, but the
    encryptor returns None when ENCRYPTION_KEY is missing/invalid in production.
    cache._dumps then writes the original portfolio payload with encrypted=false,
    so sensitive portfolio names, holdings, and share counts can be stored
    plaintext despite the production encryption requirement.

  root_cause: >
    codes/security.py lines 157-161 logs the missing production key and leaves
    cipher as None; codes/data/cache.py lines 111-118 treats a None cipher as a
    non-encrypted write instead of failing closed for encrypted kinds.

  required_fix: >
    Fail closed for encrypted cache kinds in production when encryption is not
    available. Either raise a clear configuration error before writing or make
    cache.write return False without persisting plaintext. Keep the non-production
    ephemeral-key behavior only for local development.

  acceptance_criteria:
    - In production without ENCRYPTION_KEY, portfolio cache writes do not create
      plaintext cache files.
    - Invalid ENCRYPTION_KEY fails portfolio writes instead of silently
      downgrading to plaintext.
    - Non-sensitive cache kinds such as sec_facts still write normally.
    - Tests cover missing-key and invalid-key production paths.

  risk_if_not_fixed: HIGH

---
# ISSUE_018:

 Status:[x]
  title: "Auth0 OAuth flow does not validate state parameter"
  category: security-authentication

  files:
    - codes/auth.py
    - tests/test_issue_018_auth0_state.py

  problem: >
    The Auth0 login route starts an OAuth authorization-code flow without a
    state parameter, and the callback accepts any code without validating state
    against the user's session. Same-origin POST/CSRF checks do not protect this
    GET callback, leaving the login flow exposed to OAuth login CSRF/session
    swapping risks.

  root_cause: >
    codes/auth.py lines 331-338 builds the authorize URL without state, and
    lines 340-376 never reads or verifies request.args["state"] before exchanging
    the code.

  required_fix: >
    Generate a cryptographically random state value in /login, store it in the
    server-side/session context, include it in the authorize URL, and require an
    exact constant-time match on /callback before token exchange. Clear the state
    after successful or failed validation.

  acceptance_criteria:
    - /login includes a state parameter in the Auth0 redirect.
    - /callback without state is rejected before token exchange.
    - /callback with mismatched state is rejected before token exchange.
    - /callback with matching state proceeds to token exchange.
    - Tests prove token exchange is not called when state validation fails.

  risk_if_not_fixed: HIGH

---
# ISSUE_019:

 Status:[x]
  title: "Importing codes eagerly loads the full data/model stack"
  category: performance-testing

  files:
    - codes/__init__.py
    - tests/test_security.py
    - tests/test_issue_014_portfolio_cache_keys.py
    - tests/test_issue_016_metadata_backfill.py

  problem: >
    Importing lightweight modules through `from codes import security` or
    `from codes import portfolio` executes codes/__init__.py, which eagerly
    imports data fetchers, SEC data, models, engine modules, and portfolio code.
    This makes small security/cache tests require heavy optional/runtime
    dependencies like pandas and increases import/startup cost for unrelated
    modules.

  root_cause: >
    codes/__init__.py lines 14-23 imports nearly every subpackage at package
    import time to register compatibility aliases.

  required_fix: >
    Make package initialization lazy. Avoid importing data/model/engine modules
    from codes/__init__.py just to expose aliases; use explicit imports at call
    sites, lazy __getattr__, or a narrow compatibility layer that does not load
    the full market-data stack for unrelated modules.

  acceptance_criteria:
    - `import codes.security` or `from codes import security` does not import
      pandas/sec_data/api_fetcher.
    - Targeted security/cache tests collect without loading the full data stack.
    - Backward-compatible imports still work for documented legacy module paths.
    - Import-time benchmark for a lightweight module is materially lower.

  risk_if_not_fixed: MEDIUM

---
# ISSUE_020:

 Status:[X]
  title: "Portfolio simulation callback has no rate limit or subscription gate"
  category: performance-authorization

  files:
    - codes/app_modules/tabs/portfolio.py
    - codes/portfolio.py
    - codes/app_modules/rate_limit.py
    - codes/services/permissions.py
    - tests/test_issue_020_portfolio_sim_limits.py

  problem: >
    Portfolio simulation can run expensive 10-year backtests, Monte Carlo
    projections, split lookups, and optional comparison/weak-link analysis from
    a Dash callback without the shared rate limiting or paid-feature checks used
    by analysis and factor-lab backtests. A user can repeatedly trigger this
    path and consume CPU/network resources.

  root_cause: >
    codes/app_modules/tabs/portfolio.py lines 685-690 calls
    portfolio_engine.run_simulation() directly after get_user_id(), with no
    check_rate_limit() call and no permissions.can_access_feature() gate for
    backtest/simulation access.

  required_fix: >
    Apply the shared per-user rate limiter to portfolio simulations and decide
    whether simulations are a paid BACKTEST feature. If paid, gate the callback
    with permissions.can_access_feature() and record usage only after successful
    simulation. Return clear upgrade/rate-limit messages to the UI.

  acceptance_criteria:
    - Repeated simulation clicks are rate-limited per user.
    - Trial/free users cannot run premium simulation work if simulations are
      classified as BACKTEST.
    - Paid users can run simulations within the configured limit.
    - Tests cover allowed, rate-limited, and unauthorized simulation paths.

  risk_if_not_fixed: MEDIUM

---
---
# ISSUE_021:

 Status:[x]
  title: "Tracked rejected patch artifact remains in source tree"
  category: repository-hygiene

  files:
    - codes/portfolio.py.rej
    - .gitignore

  problem: >
    codes/portfolio.py.rej is tracked in git. Rejected patch artifacts contain
    stale implementation fragments, can confuse audits/searches, and may be
    accidentally packaged or interpreted as source context by future agents.

  root_cause: >
    A failed patch/rebase artifact was committed or left tracked instead of
    being removed after the corresponding portfolio comparison work landed in
    codes/portfolio.py.

  required_fix: >
    Delete codes/portfolio.py.rej after confirming no unique logic remains only
    in the rejection file. Add a general *.rej ignore rule so future rejected
    patch artifacts are not accidentally tracked.

  acceptance_criteria:
    - codes/portfolio.py.rej is removed from git.
    - .gitignore includes *.rej.
    - rg --files no longer lists any .rej files.
    - Portfolio comparison tests still pass after removal.

  risk_if_not_fixed: LOW

---
# ISSUE_022:

 Status:[x]
  title: "Environment template is missing and .gitignore has a typo"
  category: configuration-developer-experience

  files:
    - .gitignore
    - .env.example
    - AUTHENTICATION_SETUP.md
    - SETUP_QUANT.md

  problem: >
    .gitignore contains ".ev.example" instead of ".env.example", and the repo
    does not provide a committed .env.example template. New developers must
    infer required environment variables from several docs and modules, while
    the typo makes it unclear whether an example env file was intended.

  root_cause: >
    The ignore rule appears to contain a misspelling, and configuration
    documentation is spread across setup/auth/payment/data modules rather than
    captured in one sanitized template.

  required_fix: >
    Replace the typo with an intentional rule set, add a sanitized .env.example
    containing variable names and safe placeholder values only, and update setup
    docs to point at it. Keep real .env ignored.

  acceptance_criteria:
    - .gitignore keeps .env ignored and no longer contains the .ev.example typo.
    - .env.example is committed with no real secrets.
    - Setup docs reference copying .env.example to .env.
    - Secret-scanning/search confirms no real credentials were added.

  risk_if_not_fixed: LOW

---
# ISSUE_023:
Status:[x]
  Create a dedicated, permanent analysis page for every supported company.

Example:

factorresearch.com/analyze/apple

factorresearch.com/analyze/microsoft

factorresearch.com/analyze/nvidia

Each company page will act as a historical research hub containing both FactorResearch’s standard analysis and the subscriber’s private custom-model results.

**Page layout:**

The desktop page will use a two-column layout.

**Left Column — FactorResearch Historical Analysis**

Available to all users permitted by their subscription tier.

Display all historical analyses generated using the official FactorResearch formulas.

Each analysis record should include:

- Analysis date and time
- Composite score
- Valuation verdict
- Margin of safety
- Graham score
- Piotroski F-Score
- Altman Z-Score
- Beneish M-Score
- Ohlson O-Score
- Quality, profitability, growth, momentum, and risk scores
- Price at the time of analysis
- Current price comparison
- Score changes since the previous analysis
- Link to the complete historical report

Historical URLs should remain permanent and indexable where appropriate.

Example:

factorresearch.com/analyze/apple/2026-07-09

Only analyses produced using official FactorResearch algorithms should be included in the public historical dataset.

User-created formulas must not modify, replace, or become part of the official company history.

**Right Column — Subscriber Custom Analysis**

Available only to higher-priced subscription tiers.

Display analyses generated by the signed-in subscriber using their own saved and backtested formulas.

Each custom analysis record should include:

- Custom formula name
- Analysis date
- Custom composite score
- Formula version used
- Selected factors and weights
- Backtest summary
- Performance against the default FactorResearch formula
- Performance against the selected benchmark
- Saved notes
- Link to the complete custom analysis

This column is private and specific to the signed-in user.

Custom analysis results must never be publicly indexed or exposed to another user.

Users without access should see a subscription upgrade panel explaining the custom-formula history feature without revealing private analysis data.

**Responsive behavior:**

- Desktop: two-column layout
- Tablet: adjustable two-column layout or stacked sections
- Mobile: tabbed interface

Suggested mobile tabs:

FactorResearch History | My Custom Models

The official FactorResearch history should appear first by default.

**Company-specific visual identity:**

Each company page should feel visually distinct while remaining part of the FactorResearch design system.

The page can derive its visual treatment from approved company metadata, including:

- Company logo
- Primary brand colour
- Secondary brand colour
- Industry
- Sector
- Company website styling
- Product imagery or abstract brand-inspired background elements

Examples:

- Apple: minimal layout, neutral colours, large spacing, subtle gradients
- NVIDIA: dark interface with green highlights
- Coca-Cola: red accents and classic consumer-brand styling
- JPMorgan: structured financial layout with blue accents
- Tesla: high-contrast layout with bold typography

Company branding should only influence the presentation layer.

Navigation, typography hierarchy, analysis components, accessibility, and data interpretation must remain consistent across the FactorResearch platform.

Avoid directly copying another company’s website. The design should be inspired by its public brand identity while remaining recognizably FactorResearch.

**SEO and page metadata:**

Each public company page should include unique metadata:

Title:

Apple Stock Analysis, Valuation and Historical Scores | FactorResearch

Description:

View Apple’s historical valuation, financial strength, risk scores, intrinsic value estimates, and FactorResearch analysis history.

The page should also include:

- Canonical URL
- Company name and ticker in the page heading
- Structured data where appropriate
- Internal links to related companies
- Links to sector and industry pages
- Server-rendered or crawlable summary content
- Open Graph metadata for sharing
- Sitemap inclusion

Custom subscriber analysis must not appear in public metadata, structured data, page source, or search indexes.

**URL structure:**

/analyze/<company-slug>

/analyze/<company-slug>/<analysis-date>

/analyze/<company-slug>/custom/<analysis-id>

Examples:

/analyze/apple

/analyze/apple/2026-07-09

/analyze/apple/custom/a8f4d2

Company slugs should use the company name rather than relying only on the ticker.

The ticker should remain stored as the internal company identifier so company-name changes do not disconnect historical records.

**Required implementation:**

1. Create a permanent company landing page for every supported security.
2. Store official analysis snapshots separately from user-created analysis snapshots.
3. Build the two-column historical-analysis interface.
4. Add subscription-tier checks for the custom-model column.
5. Add user-level access controls for custom analysis records.
6. Generate company-specific design tokens from approved brand metadata.
7. Create permanent URLs for official historical analyses.
8. Add private URLs for custom analyses.
9. Add SEO metadata, canonical tags, structured data, and sitemap support.
10. Add score-change and price-performance comparisons between analysis dates.

**Constraints:**

- Official and custom analysis histories must use separate database tables or clearly isolated data models.
- Custom analysis must only be visible to its owner.
- Custom analysis pages must use noindex.
- Company styling must preserve accessibility and readable contrast.
- Company logos and brand assets must be sourced and used in compliance with applicable trademark and licensing rules.
- Historical analysis records should be immutable after publication, except for clearly documented data corrections.
- Re-running an analysis must create a new snapshot rather than overwrite an older report.
- Delisted companies must retain their historical pages.
- Page performance must not depend on loading every historical report at once.
- Historical lists should use pagination or incremental loading.
- The company theme must not alter the meaning or colour interpretation of financial warnings, risk levels, or verdict badges.

**Acceptance criteria:**

- Visiting /analyze/apple opens Apple’s permanent analysis page.
- The left column displays all official FactorResearch analysis snapshots for Apple.
- Eligible subscribers see their private custom-formula analysis history in the right column.
- Standard subscribers see an upgrade prompt instead of the custom history.
- One user cannot access another user’s custom analyses by changing the URL.
- Every official historical analysis has a permanent URL.
- Custom analyses are excluded from search indexing and public sitemaps.
- Each company page has a visually distinct company-inspired identity.
- The page remains recognizably part of the FactorResearch platform.
- The interface works correctly on desktop, tablet, and mobile.
- Historical reports show the stock price and score at the time of analysis.
- The system clearly distinguishes official FactorResearch results from user-created model results.
- Re-running an analysis does not overwrite an existing historical result.

**Risk if not implemented:** MEDIUM

Without permanent company analysis pages, FactorResearch loses opportunities for organic search traffic, long-term research history, repeat visits, and differentiation between its official methodology and subscriber-created investment models.


**User Access Model**

**Trial User**

**Purpose:**

Allow users to experience the platform value before requiring payment.

Limits:

- ✅ Maximum 3 company analyses
- ✅ View full company analysis
- ✅ View Graham/Buffett/Quality scores
- ✅ Adjust custom factor weights
- ✅ Preview personalized composite score
- ❌ No historical backtesting
- ❌ No saved strategies
- ❌ No portfolio analytics
- ❌ No unlimited screening

After the third analysis:

Display upgrade prompt:

You have used your 3 free analyses.

Unlock IntrinsicIQ Premium:

✓ Unlimited company analysis

✓ Custom investment strategies

✓ Historical backtesting

✓ Portfolio analytics

✓ Strategy tracking

**Premium Features**
**Unlimited Analysis**

Unlock:

- Unlimited company research
- Unlimited factor scoring
- Unlimited custom weighting
- Full screening capabilities

Implementation:

Add user entitlement check before analysis execution.

Example:

request analysis

|

▼

check subscription status

trial_remaining > 0

|

▼

allow analysis

decrement counter

OR

premium_user

|

▼

allow unlimited access

**Custom Factor Weighting**

**Status: Existing functionality**

Allow all trial users to experiment with custom formulas.

Example:

Default:

Graham       25%

Buffett      25%

Quality      20%

Health       15%

Growth       10%

Momentum      5%

User customization:

Graham       50%

Buffett       0%

Quality      30%

Health       20%

Growth        0%

Momentum      0%

The personalized score calculation remains available during trial.

Purpose:

Increase user engagement and demonstrate value.

**Backtest Engine Premium Gate**

**Highest-value premium feature**

Backtesting requires subscription.

Before execution:

User clicks "Run Backtest"

|

▼

check subscription

premium?

|

├── Yes

│      Run backtest

│

└── No

Show upgrade prompt

**Backtest Entitlement Levels**

**Premium**

Includes:

- Custom weight backtesting
- Historical performance
- CAGR
- Sharpe
- Maximum drawdown
- Strategy comparison

**Professional (Future)**

Includes:

- Large universe backtesting
- Daily rebalance
- Factor optimization
- Monte Carlo simulation
- API access
- Export research data

 **Required Database Changes**

 **User Subscription Table**

New table:

subscriptions

id

user_id

plan

status

start_date

end_date

stripe_customer_id

stripe_subscription_id

Plans:

trial

premium

professional

cancelled

 **User Usage Tracking**

New table:

user_usage

user_id

analysis_count

period_start

period_end

feature_usage

Track:

company_analysis

screening_runs

backtests

portfolio_analysis

 **Feature Permission Layer**

Create centralized permission service:

New file:

codes/services/permissions.py

Responsibilities:

can_access_feature(

user,

feature_name

)

Examples:

can_access_feature(

user,

"backtest"

)

returns:

True / False

Features:

ANALYSIS

CUSTOM_WEIGHTS

SCREENING

BACKTEST

PORTFOLIO_ANALYTICS

EXPORT

Avoid scattering subscription checks throughout the application.

**UI Changes**

Add:

UpgradeBanner

FeatureLockedModal

UsageCounter

Examples:

Trial:

2 / 3 free analyses remaining

Locked feature:

Historical backtesting requires Premium

Unlock strategy validation →

 **Stripe Integration**

Files:

codes/payments/

stripe_client.py

subscriptions.py

webhooks.py

Implement:

- Checkout session creation
- Subscription status sync
- Cancellation handling
- Payment failure handling
- Webhook validation

#**Analytics Tracking**

Track conversion funnel:

Events:

analysis_completed

custom_weight_created

backtest_clicked

upgrade_viewed

subscription_started

Important funnel:

Company Analysis

↓

Custom Strategy Created

↓

Backtest Attempted

↓

Subscription Conversion

 **Acceptance Criteria**

- Trial users are limited to 3 company analyses.
- Trial usage persists across sessions.
- Premium users have unlimited analysis access.
- Custom weighting works for trial and premium users.
- Backtesting requires an active subscription.
- Feature restrictions are enforced server-side.
- Subscription status updates automatically from payment provider.
- Users receive clear upgrade prompts when hitting limits.
- Existing factor engine and backtest engine continue working without major refactoring.

 **Future Enhancement**

Introduce usage-based premium tiers:

Premium:

Normal backtests

Professional:

Large universe research

Institutional:

API + bulk research

The architecture should support additional paid tiers without rewriting feature access logic.

---
# ISSUE_024
Status: [x]
**Objective:**

Finish the client-facing subscription conversion funnel so trial users hit a clear, consistent buy path instead of only seeing scattered upgrade text in feature gates.

The core entitlement checks from ISSUE_008 already exist. What remains is the conversion experience:

- A dedicated upgrade / pricing surface that explains trial vs premium vs professional
- A single reusable upgrade banner/modal pattern instead of feature-specific ad hoc messages
- Consistent CTA routing to checkout or the pricing surface
- Funnel analytics for upgrade views and clicks so conversion can be measured

**Current Gaps**

- Analyze and Factor Lab already block gated features, but the buy experience is embedded inside feature callbacks.
- There is no dedicated plan comparison / pricing page.
- Upgrade prompts are plain text or inline links, not a consistent branded conversion component.
- No visible analytics events are emitted for upgrade view/click/conversion steps.
- one portfolio simulation for freemium users is allowed

**Required Next Step**

Create a client-ready conversion flow that:

1. Surfaces a dedicated pricing / upgrade view from every locked feature.
2. Reuses a single UI pattern for locked states across analyze, backtest, and future premium features.
3. Routes all buy CTAs through the billing entry point.
4. Records funnel events for upgrade_viewed, upgrade_clicked, and subscription_started.

**Files**

- codes/app_modules/layout.py
- codes/app_modules/tabs/analyze.py
- codes/app_modules/tabs/factor_lab.py
- codes/billing.py
- codes/services/permissions.py
- codes/payments/webhooks.py
- codes/app_modules/tabs/pricing.py

**Acceptance Criteria**

- Trial users see a clear pricing / upgrade view when they hit a lock.
- The same upgrade component is reused across analysis, backtesting, and future premium gates.
- All buy CTAs resolve through the billing flow.
- Upgrade view and click events are tracked.
- Premium users continue to bypass the prompt and use features normally.

---
# issue_025

**Status:** [x]

**Problem**
    
update the layout form and structure of Financial Health,Stability Score,Market Regime,FCF Quality,Capital Allocation,Growth Quality,Alternative Data,Options Signal,Factor Momentum to match other cards , so similar css applys , and their html and class codes improves.

---
# ISSUE_026

**Status:** [x]

**Title:** Implement Product Analytics Platform

**Category:** analytics

**Estimated effort:** 3--5 days (initial integration), ongoing expansion

**Current State**

Core implementation for the current product surface is complete. The
codebase now has a working event collection foundation, persistence
layer, instrumentation across the implemented product flows, and
session-level server-side opt-out support.

The current codebase now has:

-   async, best-effort product event tracking
-   a dedicated `analytics_events` persistence path
-   optional analytics DB URL support via `DATABASE_ANALYTICS_URL`
-   fallback to `DATABASE_MARKET_URL` if a separate analytics DB is not
    configured
-   optional third-party script bootstrap via env vars for:
    -   PostHog
    -   Microsoft Clarity
    -   Sentry

Implemented domain events currently include:

-   `stock_viewed`
-   `analysis_started`
-   `analysis_completed`
-   `analysis_failed`
-   `algorithm_selected`
-   `screener_run`
-   `screener_filter_changed`
-   `portfolio_created`
-   `portfolio_updated`
-   `backtest_started`
-   `backtest_completed`
-   `backtest_failed`
-   `pricing_page_viewed`
-   `subscription_started`
-   `subscription_completed`

These are wired into the existing app flows and do not block product
behavior if analytics writes fail.

------------------------------------------------------------------------

## What Has Already Been Done

### Phase 1 foundation

-   optional PostHog snippet injection
-   optional Microsoft Clarity snippet injection
-   optional Sentry browser snippet injection
-   env-driven setup instead of hardcoding vendor config

### Phase 2 foundation

-   product analytics service created
-   event writes made asynchronous / best-effort
-   `analytics_events` table added
-   read/query helpers added for:
    -   recent events
    -   event counts by event name
    -   top metadata values by event/key
-   page path, user id, anonymous id, timestamp, and metadata are stored
-   usage-counter summaries for events are still maintained for quick
    aggregate counts
-   analysis and backtest completion/failure events now include explicit
    runtime metadata
-   analysis and backtest completion events now include cache-hit
    metadata where available
-   analysis and backtest failure events now include normalized
    `failure_class` metadata for reporting/debug queries
-   session-level app analytics opt-out now suppresses server-side event
    tracking beyond the env-level global disable flag

### Implemented instrumentation points

-   Analyze flow
-   Screener ticker clicks / country filter changes / screener run
-   Factor Lab backtests / algorithm selection
-   Portfolio create/update/simulation flows
-   Pricing page views
-   Checkout/subscription completion webhook

------------------------------------------------------------------------

## Post-Launch Ownership

All remaining production validation, rollout, and optional reporting
expansion for ISSUE_026 has been moved to `Publish.md` under
`ISSUE_026_ANALYTICS_OPERATIONS`.

------------------------------------------------------------------------

## Privacy / Safety Notes

-   Anonymous tracking exists for guest-style sessions
-   User-linked events exist after authentication or session identity
-   Analytics failures should not break user workflows
-   Sensitive financial payloads should continue to be minimized in event
    metadata

------------------------------------------------------------------------

## Acceptance Criteria For Marking This Fully Complete Later

-   Generic analytics are actually configured and verified in third-party
    platforms.
-   Domain-specific financial events are stored in a dedicated analytics
    pipeline.
-   Analytics collection remains asynchronous and non-blocking.
-   Product dashboards or query surfaces answer the core business and
    product questions from this issue.
-   Funnel analysis is queryable from landing/page interaction through
    subscription completion.
-   Future recommendation/reporting systems can build on this data.




---
# ISSUE_027:
  **Status:** [x]
  title: recomendation labels

  algorithim should never produce these word: BUY,SELL,HOLD. for legal reason we need to play around with the word, ENHANCED_VERDICTS from scorer.py is a good anchor, all 
  buy and sell signal must get their information from there, this includes, option signal and any other signal in future
---
# ISSUE_028:
  **Status:** [x]
  title: developer qa

  create a solution that in development mode, dev can easily pretend to be different user type, paid free and pro. make it so it is exapndable in future

# ISSUE_029:
**Status:** []
title: alt data not complete

context: every time run analysis we get a same alt data, just available,planned, it looks like it is not completly wired up and working
files: alternative_data.py

implementation status:
- [x] Phase 1 — SEC 8-K sentiment is already wired into analysis through the free SEC EDGAR feed and cached filing text. Verified by `tests/test_sec_8k_filings.py`.
- [x] Phase 1 — provider configuration diagnostics: placeholder credentials (for example `your_api_key_here`) are no longer treated as live. Insider, institutional ownership, and patent cards now show `CONFIGURATION_REQUIRED` instead of silently remaining generic placeholders.
- [ ] Phase 2 — add a real `FINNHUB_API_KEY` with entitlement for insider transactions, institutional ownership, and USPTO patents. The current `.env` value is a placeholder, so these provider calls cannot return records yet.
- [ ] Phase 3 — add dedicated providers and scheduled storage for hiring velocity, web traffic, and supply-chain relationships; FMP/Finnhub do not supply those complete datasets.
- [ ] Phase 4 — add freshness/source timestamps and a background refresh job before treating alternative data as production-ready.

# ISSUE_030:
**Status:** [x]
title: TOC and Privacy

context: both page are currenlty empty and open in new page

solution: fill both page with legal content, and make them open as popup with same look and feel as rest of the application, popups up should not take the whole page but allow user to make them whole page.

# ISSUE_031 — Pricing + Conversion System (Master)

Status: [x]

title: Implement simplified pricing model + conversion-driven upgrade system (Free → Premium)

category: monetization / product-growth / authorization

---

## Overview

Refactor pricing into a conversion-driven system:

FREE → hook user  
PREMIUM → monetize core value (backtesting)

---

## Core Rules

- Only 2 tiers at launch: FREE + PREMIUM
- Backtesting = main conversion trigger
- Centralized pricing logic
- Consistent upgrade UI across app

---

## Tiers

### FREE
- 3 analyses
- full breakdown
- custom weights
- NO backtesting
- NO portfolio analytics

### PREMIUM
- unlimited analysis
- portfolio tools
- backtesting
- full history

---

## Acceptance Criteria

- Only 2 plans exist
- Backtest is gated
- Analysis limit enforced
- Upgrade prompts consistent
- Stripe integration aligned

---

# ISSUE_031A — Backend (Permissions + Pricing Engine)

Status: [x]

category: backend / authorization

files:
- codes/services/permissions.py
- codes/services/pricing.py
- codes/data/db.py

---

## Required Fix

Create centralized pricing config:

```python
PLANS = {
    "free": {
        "analysis_limit": 3,
        "features": ["ANALYSIS", "CUSTOM_WEIGHTS"]
    },
    "premium": {
        "analysis_limit": None,
        "features": ["ANALYSIS", "CUSTOM_WEIGHTS", "BACKTEST", "PORTFOLIO_ANALYTICS"]
    }
}
```

---

## Logic

- FREE → limited analysis, no backtest
- PREMIUM → full access

---

## Acceptance Criteria

- can_access_feature() uses PLANS
- analysis limits enforced server-side
- no scattered entitlement logic

---

# ISSUE_031B — UI (Upgrade System)

Status: [x]

category: frontend / conversion

files:
- codes/app_modules/components/upgrade_banner.py
- codes/app_modules/components/feature_lock_modal.py
- codes/app_modules/tabs/analyze.py
- codes/app_modules/tabs/factor_lab.py
- codes/app_modules/tabs/portfolio.py

---

## Required Fix

Create reusable UI:

### UpgradeBanner
- shows usage (2/3 analyses)
- triggers upgrade

### FeatureLockedModal
Used when:
- backtest clicked
- portfolio locked

---

## Modal Copy

Title:
Does your strategy actually work?

Body:
Test your strategy using historical data

CTA:
Unlock Premium

---

## Acceptance Criteria

- Same modal used everywhere
- Triggered on backtest click
- Banner shows usage state

---

# ISSUE_031C — Payments + Stripe Integration

Status: [x]

category: payments

files:
- codes/billing.py
- codes/payments/stripe_client.py
- codes/payments/webhooks.py

---

## Required Fix

Align Stripe with 2-tier system:

- free → no subscription
- premium → active subscription

---

## Webhook Logic

- subscription_created → set premium
- subscription_cancelled → revert to free

---

## Acceptance Criteria

- Stripe updates user plan correctly
- Permissions reflect plan instantly
- No mismatch between billing + access


# ISSUE_032 - UI BUG:
Status: [x]
category: UI

ISSUE : footer shows up in middle of the page, and it has a white background

# ISSUE_033-engine contract
status:[x]
category: engine
files:
engine_contarct.py,app.py,billing.py, or any other files that will make this issue work

ISSUE: wire engine contract to all and allow an ability to easily set flag,add a small file so we can switch flags in that file, maybe a json file, so when flag is set to INTERNAL all billing checks turns off, we just run the app at full,but do add an ability in git so we never be allowed to push to git main branch when flag INTERNAL or BETA are set.

# ISSUE_034- analysis direct linking not working
status:[x]
category: engine
files:analysis_ui.py, app.py, analysis.py
ISSUE: trying to open this link does nothing http://127.0.0.1:8050/analyze/AAPL/20260711

# ISSUE_035- user get locked out in Company research tab
status:[x]
category: code
files:
ISSUE: [http://127.0.0.1:8050/analyze/AAPL](http://127.0.0.1:8050/analyze/AAPL) when in company page we can't navigate to analyze tab, we get stuck, if user click on analyze tab we run analyze on a company page

# ISSUE_036- error pages are missing
status:[x]
category: code
files: 404.html,401,500,403,400
ISSUE: we currently have none of these pages, they must be created with looks and feels of the application


# ISSUE_037- sign up not working
status:[x]
category: pre landing pages
files: http://127.0.0.1:8050/landing/pre-a , http://127.0.0.1:8050/landing/pre-b
ISSUE: both page currently throw an error when user try to sign up, pre-b has visual bug issue the apple analyze demo is broken and does not match our own view, and "What you
can expect
" is also broken

# ISSUE_038- light mode issue 
status:[x]
category: UI
files: .scss
ISSUE: 
  - light mode text are hard to read the color "#e8eaf0" is not readable with white background chose a darker one
  - color #00e676!important is also not easy to read    
  - insider activity have a bolder lines , all cards must match a same feel and desgin
  - in dark mode some labels are white some are greyish , unify them all to #8899aa

# ISSUE_039- option removed
status:[x]
category: UI
files: screener.py
ISSUE: 
  - option engine is not ready so it has to be removed, i have removed the card but the analytic tab needs to be ordered correctly, preffered to keep everything as pair

# ISSUE_040- Email template
status:[]
category: email
files: 
ISSUE: 
  - create email tempalate which will be used later, we will use to send people whom sign up in wait list that app is ready and for future communications

---

# ISSUE_041 - Scalable chart rendering and graph artifact caching

status: [x]

category: performance / scalability / data-visualization

priority: HIGH

files:
  - codes/app.py
  - codes/data/db.py
  - codes/data/cache.py
  - codes/services/chart_service.py
  - codes/workers/chart_worker.py
  - codes/routes/charts.py
  - codes/app_modules/components/*
  - assets/*
  - tests/test_issue_041_chart_caching.py

problem: >
  Graham App stores the underlying financial and analysis data in PostgreSQL,
  but chart datasets and graph figures are still calculated and rendered
  during user requests. As more charts are added and concurrent usage grows,
  repeated database reads, financial transformations, figure construction,
  image encoding, and response serialization can consume web-process CPU and
  memory, increase response latency, and slow down unrelated users. once completed make sure all sub branches get the copy of this fix, so when merging back we do not override the fixes

root_cause: >
  Chart preparation, chart rendering, and page delivery are coupled inside the
  request path. Identical charts may be rebuilt for every user even when the
  ticker, analysis version, source data, period, and chart configuration have
  not changed. There is no shared versioned chart cache, background chart job
  pipeline, cache-stampede protection, or dedicated object-storage path for
  generated PNG, SVG, and PDF artifacts.

current_behavior:
  - Financial and analysis data is persisted in PostgreSQL.
  - Chart data is queried and transformed when a user opens a page.
  - Figure objects are constructed repeatedly for identical requests.
  - Web processes perform chart work while also serving application requests.
  - Multiple users requesting the same uncached chart can trigger duplicate work.
  - Static graph files do not have a defined object-storage and CDN strategy.
  - Charts below the visible viewport may be prepared before the user views them.
  - Cache invalidation is not tied consistently to source-data or chart-code versions.

required_fix: >
  Introduce a shared chart-delivery architecture that separates source data,
  prepared chart datasets, interactive browser rendering, and static chart
  artifacts.

  1. Chart data service

     Create a centralized chart service responsible for:
       - loading the minimum required database records;
       - producing normalized JSON-ready chart datasets;
       - generating deterministic cache keys;
       - returning cached data before performing calculations;
       - recording generation time, cache status, and errors.

     Application callbacks and routes must not duplicate chart-building logic.

  2. Browser-side interactive rendering

     Interactive charts should be rendered in the user's browser from prepared
     JSON datasets whenever practical.

     The server should return data and chart configuration rather than repeatedly
     rendering complete figures or image files during every request.

     Existing Dash/Plotly charts may remain supported, but expensive reusable
     data preparation must be moved behind the chart service and shared cache.

  3. Versioned cache keys

     Cache keys must include all inputs that can change chart output, including:

       chart:{ticker}:{chart_type}:{period}:{data_version}:{analysis_version}:{chart_schema_version}:{config_hash}

     User-specific or custom-formula charts must include a normalized,
     deterministic configuration hash. Raw user formulas, email addresses,
     names, or other personally identifiable information must not appear in
     cache keys.

  4. Cache storage

     Use Redis or another deployment-wide shared cache for prepared chart JSON
     and short-lived generation locks.

     The cache must be shared across web processes and application instances.
     A process-local dictionary alone is not sufficient for production.

  5. Data-version invalidation

     Historical charts should remain cached until their source data changes.

     When a new filing, market-data revision, analysis version, or chart-schema
     version is introduced, the generated cache key must change automatically.
     Avoid broad wildcard deletion when versioned keys can make old entries
     unreachable safely.

  6. Background generation

     Add a dedicated chart worker using the project's approved job framework.

     After a standard company analysis or financial-data refresh completes,
     enqueue generation of commonly viewed chart datasets.

     The worker must:
       - be idempotent;
       - deduplicate jobs;
       - retry transient failures with limits;
       - record failures without breaking the completed company analysis;
       - avoid regenerating an artifact that already exists for the same version.

     Rare, user-specific, or advanced charts may be generated on first request
     and then cached.

  7. Cache-stampede protection

     Use a distributed lock or equivalent single-flight mechanism so multiple
     users cannot rebuild the same missing or expired chart simultaneously.

     After acquiring the lock, check the cache again before generating data.

  8. Stale-while-revalidate

     When a usable stale chart exists, return it immediately and enqueue one
     refresh job rather than blocking the user.

     The response should expose chart freshness metadata where useful, without
     presenting stale market-sensitive data as current.

  9. Static chart artifacts

     PNG, SVG, and PDF chart files used for exports, reports, SEO pages, social
     sharing, or email must be generated outside the normal web request path.

     Store static artifacts in S3-compatible object storage such as Cloudflare
     R2 rather than PostgreSQL or the web server's local filesystem.

     PostgreSQL should store only artifact metadata, including:
       - ticker;
       - chart type;
       - source data version;
       - analysis version;
       - chart schema version;
       - object key;
       - generation status;
       - generated timestamp;
       - content type;
       - checksum;
       - error details.

     Serve public or authorized artifacts through a CDN or signed URL as
     appropriate.

  10. Lazy loading

      Charts below the fold, inside unopened sections, tabs, carousels, or
      accordions must not be fetched or initialized until the user approaches
      or opens the relevant section.

      The initial company-analysis page should prioritize summary content and
      visible charts.

  11. Generation policy

      Do not pre-render every chart for every security.

      Use the following policy:
        - primary company-page charts: precompute after standard analysis;
        - common model charts: precompute or generate on first request;
        - rare advanced charts: generate on first request and cache;
        - custom user charts: generate on demand using a configuration hash;
        - export/share/SEO images: background worker plus object storage;
        - live or intraday charts: short-lived cached data rendered in browser.

  12. Failure behavior

      A chart-generation failure must not make the full analysis page fail.

      Return a chart-specific unavailable state with retry capability and log a
      normalized failure class. Do not expose internal exceptions to users.

constraints:
  - PostgreSQL remains the source of truth for financial and analysis data.
  - Do not store large PNG, SVG, or PDF binary payloads directly in PostgreSQL.
  - Do not rely only on process-local memory caching in production.
  - Do not recompute financial models solely to display an already-computed chart.
  - Chart caching must never leak private custom strategies or portfolio data
    between users.
  - Public standard-analysis charts may be shared globally when their complete
    inputs are identical.
  - User-specific chart authorization must be checked before returning cached
    data or signed artifact URLs.
  - Live market-sensitive charts must use freshness rules appropriate to their
    data source.
  - Chart generation and cache failures must not interrupt core analysis storage.
  - Existing chart output and interpretation must remain functionally consistent
    unless a chart schema version is intentionally changed.

observability:
  - Track chart cache hit and miss counts.
  - Track stale responses and background refreshes.
  - Track generation duration by chart type.
  - Track chart payload size.
  - Track worker queue depth and job duration.
  - Track generation failures by normalized failure class.
  - Track distributed-lock wait and timeout counts.
  - Track object-storage upload failures.
  - Track page-level time to first visible chart.

acceptance_criteria:
  - Repeated requests for the same ticker, chart type, period, data version,
    analysis version, schema version, and configuration reuse one cached result.
  - Two concurrent requests for the same uncached chart cause no more than one
    chart-generation execution.
  - Interactive chart rendering is moved to the browser where practical, while
    expensive server-side data preparation is reused from a shared cache.
  - Common chart datasets can be generated by a worker after analysis completion.
  - Rare and custom charts are generated on demand and cached deterministically.
  - A new filing or changed source-data version produces a new chart cache key.
  - A changed chart implementation increments chart_schema_version and does not
    reuse incompatible cached output.
  - Charts below the fold are lazy-loaded rather than prepared during initial
    page rendering.
  - Static PNG, SVG, and PDF artifacts are generated outside the normal web
    request path and stored in object storage.
  - PostgreSQL contains artifact metadata only, not large chart binaries.
  - A chart-generation failure displays a chart-specific unavailable state and
    does not break the rest of the analysis page.
  - Authorization tests prove cached custom charts and private artifacts cannot
    be accessed by another user.
  - Tests cover cache hit, cache miss, version invalidation, configuration hash,
    concurrent single-flight generation, stale-while-revalidate, worker
    idempotency, and failure isolation.
  - Load testing demonstrates that cached chart requests do not trigger repeated
    financial calculations or database-heavy graph transformations.
  - Production dashboards expose cache-hit rate, generation latency, worker
    failures, and time to first visible chart.

implementation_phases:

  phase_1_shared_chart_data_cache:
    - Create the centralized chart service.
    - Add deterministic versioned cache keys.
    - Cache normalized chart JSON in shared Redis.
    - Add lazy loading for non-visible charts.
    - Add cache-hit and generation-latency instrumentation.

  phase_2_workers_and_concurrency:
    - Add idempotent background chart jobs.
    - Precompute primary chart datasets after analysis completion.
    - Add distributed single-flight locking.
    - Add stale-while-revalidate behavior.
    - Add retry limits and chart-specific failure states.

  phase_3_static_artifacts_and_cdn:
    - Add chart artifact metadata storage.
    - Generate export, SEO, social, and report images in workers.
    - Store files in S3-compatible object storage.
    - Serve artifacts through a CDN or authorized signed URLs.
    - Add retention and cleanup rules for unreachable old versions.

risk_if_not_fixed: HIGH

---
# AI EXECUTION PROTOCOL

When fixing an issue:

1. Identify issue in this file
2. Read ONLY listed files
3. Confirm root cause
4. Apply minimal patch
5. Add or update tests
6. known issues are always in main branch, so they must be tested before they are pushed to git
7. once an issue has been fixed and pushed to main, other branches start downloading the correct files, if it is shared among them, this way we do not have confilict merge
8. never write inline css alwasys use external scss file
9. STOP

---

# NON-NEGOTIABLE RULES

* No repo-wide scans
* No unrelated refactors
* No multi-issue fixes per run
* No guessing missing logic
* Ask if uncertain
