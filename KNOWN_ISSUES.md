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

- Read **only**: `KNOWN_ISSUES.md`, `AI_CONTEXT.md`, `PROJECT_MAP.md`
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

## ISSUE_001:
   
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

## ISSUE_002:
   
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

## ISSUE_003:

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
## ISSUE_012:

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

## ISSUE_013:

Status: [ ]

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
**TEST RULE**: Add minimal test `test_issue_XXX_*.py` when needed.

# AI EXECUTION PROTOCOL

When fixing an issue:

1. Identify issue in this file
2. Read ONLY listed files
3. Confirm root cause
4. Apply minimal patch
5. Add or update tests
6. push to git
7. STOP

---

# NON-NEGOTIABLE RULES

* No repo-wide scans
* No unrelated refactors
* No multi-issue fixes per run
* No guessing missing logic
* Ask if uncertain
