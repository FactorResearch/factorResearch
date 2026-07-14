# AI_CONTEXT.md

## Project Overview

This repository is a fundamental investing and portfolio analytics platform.

The goal is to produce accurate financial quality scores, valuation metrics, and portfolio risk estimates.

Correctness is more important than code elegance.

---

## Engineering Priorities

Priority Order:

1. Mathematical correctness
2. Financial-model correctness
3. Reproducibility
4. Test coverage
5. Performance
6. Refactoring

Do not refactor unless explicitly requested.

---

## Development Philosophy

Prefer:

* Small targeted fixes
* Minimal diffs
* Localized changes
* Additional tests

Avoid:

* Architecture rewrites
* Broad cleanup efforts
* Style-only modifications
* Renaming unrelated code

---

## Financial Model Standards

### Graham

Use consecutive dividend years.

Do not count non-continuous dividend history.

---

### Piotroski

Year-over-year comparisons must use fiscal periods approximately one year apart.

Never compare arbitrary adjacent statements.

---

### Altman

Missing components should not artificially depress scores.

Partial scores must be normalized by available-weight fraction.

---

### Greenblatt

Net Working Capital excludes cash and equivalents.

Use enterprise-value-based earnings yield.

---

### Portfolio Analytics

Portfolio volatility must use covariance matrices.

Do not assume assets are independent.

Monte Carlo simulations should use geometric drift:

μ_geo = μ_arith − σ²/2

---

### Risk Metrics

Sortino downside deviation must be calculated using total observations (N), not downside observations only.

---

## AI Working Instructions

Before changing code:

1. Verify issue exists.
2. Identify exact functions affected.
3. Explain root cause.
4. Propose minimal patch.

Only then implement.

---

## Required Output Format

For every change provide:

### Files Modified

* file name
* reason

### Logic Change

* old behavior
* new behavior

### Tests

* tests added
* tests updated

### Risks

* assumptions
* edge cases

---

## Repository Constraints

Preserve:

* Public APIs
* Existing output formats
* Existing CLI behavior
* Existing UI behavior

Unless explicitly instructed otherwise.

Any request to implement work from `roadMap.md` is future-version work. Do not
implement roadmap items directly on `main`.

For every roadmap version or major development phase, create and work on a
dedicated git branch named after that version number, for example `v2.0` or
`v2.1`.

Keep roadmap branches easy to merge:

* Scope each branch to its roadmap version or phase.
* Keep branches updated from `main` when `main` changes.
* If updating from `main` causes a merge conflict, stop and ask before
  resolving it.
* Avoid unrelated refactors or broad cleanup in roadmap branches.

Every newly added scoring/model engine must include cached-analysis upgrade
support for existing `analysis_cache` rows in Postgres.

Minimum requirement for a new model:

* compute during fresh analysis
* persist into `analysis_cache`
* persist its factor score if applicable
* backfill/enrich already analyzed stocks in DB without requiring manual
  re-analysis

---

## Token Efficiency Rules

Read only files directly related to the task.

Do not scan the entire repository.

Do not load unrelated modules.

Do not perform speculative refactoring.

Keep context focused on the requested issue.

When uncertain, ask for clarification instead of expanding scope.

---

## Definition of Done

A task is complete only if:

* Logic is corrected
* Tests pass
* No unrelated files changed
* Diff is minimal
* Behavior is documented
