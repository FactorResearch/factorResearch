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
   
 Status:[]
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
