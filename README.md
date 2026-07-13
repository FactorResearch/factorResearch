# Graham Score v2.2

Branch: `v2.2`

Status: factor-research release branch. It remains independent from `main`
until an approved release merge.

## What This Branch Does

V2.2 adds calculated factor research to historical Analyze pages. It replaces
the former "Next Models" placeholders with real model output when the required
security, benchmark and factor-return histories are available.

## Implemented Models

- CAPM: market beta, alpha, R-squared and observations.
- Fama-French 3 Factor: market, size (`SMB`) and value (`HML`).
- Fama-French 5 Factor: FF3 plus profitability (`RMW`) and investment (`CMA`).
- Carhart 4 Factor: FF3 plus momentum (`MOM`).

The regression and attribution engine is
`codes/engine/factor_research.py`. Factor datasets are loaded and normalized by
`codes/data/factor_returns.py`; they are not represented by hard-coded scores.

## Attribution Views

- Holdings attribution summarizes the analyzed security's factor exposures.
- Return attribution separates estimated factor contribution from alpha and
  residual return.
- Rolling attribution calculates time-windowed model behavior so exposure and
  contribution changes can be inspected over time.

These are both calculations and visible Analyze-page sections. They are not
placeholder model names.

## Backward Compatibility

- Existing analysis URLs and snapshots continue to work.
- When an older snapshot lacks V2.2 fields, the Analyze route attempts a
  view-time backfill using available historical data.
- Users are not required to rerun every company analysis after release.
- Calculated factor research can be persisted in the relational database for
  reuse; it is not saved as a new JSON data file.
- If required history or factor rows are unavailable, the page reports the
  missing data instead of inventing a model result.

## User Interface

The factor model grid is responsive: wider screens use columns large enough to
keep each model readable, tablets retain the compact grid, and narrow screens
stack the content. Return and rolling attribution appear beneath the model
summary when calculated data exists.

## Scope Boundaries

This branch does not include V3 institutional portfolio analytics, advanced
portfolio Monte Carlo models or production option-chain data. It also does not
guarantee a model result for a security whose price/factor histories do not
have enough aligned observations.

## Run and Verify

Use the repository's normal application startup. Existing analyses can be
opened at `/analyze/<SYMBOL>/<ANALYSIS_ID>`; the route performs compatibility
backfill when possible.

Run focused tests with:

```bash
PYTHONPATH=. pytest -q \
  tests/test_factor_returns_provider.py \
  tests/test_v22_factor_research.py \
  tests/test_v22_analyze_integration.py \
  tests/test_historical_analysis_page.py
```
