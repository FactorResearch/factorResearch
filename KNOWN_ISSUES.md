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

## ISSUE-001

Status: []

Title: Maring of safety

Priority: Normal

Files: scorer.py

* 

Problem:
*  if margin of saftey is negative from both grahm and buffet we should not advertise buy , and if we still can buy it should come with a big warning
Required Fix:
* modify buy crataria to never promot negative margin of saftey stocks to be in buy list

Acceptance Criteria:
* any stock entering negative saftey margin is no longer a buy and should be down graded to weak
* if only one , either grahm or buffet have negative margin of safety there should be new label indicating that

---

## ISSUE-002

Status: []

Title: Fix Finnhub price history failures (403 candle error) and remove unreliable historical dependency

Priority: Normal

Files: alpha_vantage_client.py

*

Problem:
* Finnhub candle endpoint is failing with 403 errors for certain symbols (e.g. ISRG)
* Example error:
  `[Finnhub SDK] candle error for ISRG: FinnhubAPIException(status_code: 403): You don't have access to this resource.`
* This causes historical price fetching to break or fall back to Alpha Vantage
* Alpha Vantage is slow, heavily rate-limited, and being overused as a fallback
* Result is inconsistent and unreliable 10-year historical datasets

Required Fix:
* Remove Finnhub as a source for historical price data (`stock_candles`)
* Finnhub must NOT be used for:
  - price history
  - OHLC candles
  - multi-year data aggregation
* Use FMP (Financial Modeling Prep) as the primary and stable source for historical prices
* Implement FMP endpoint for historical data:
  - `/api/v3/historical-price-full/{symbol}`
* Ensure data supports at least 10 years of monthly price history
* Keep Finnhub ONLY for real-time quotes (`quote()`), if needed
* Reduce or eliminate Alpha Vantage dependency where possible
* Simplify fallback logic:
  - Historical data: FMP → (optional fallback Alpha Vantage)
  - Real-time price: Finnhub → fallback FMP quote
* Remove Finnhub candle rate-limit and retry logic since it will no longer be used for history

Acceptance Criteria:
* No calls to `finnhub.stock_candles()` remain in production code
* Fetching historical data for symbols (e.g. ISRG, AAPL, MSFT) always returns:
  - no errors
  - consistent 10-year dataset
* No 403 Finnhub permission errors occur in historical data flows
* System no longer relies on Alpha Vantage as primary or frequent fallback for history
* FMP successfully provides all historical datasets required for Graham-style analysis
* Finnhub is only used for real-time pricing (if retained) and does not affect historical reliability

---


# CLOSED ISSUES


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
