# Graham Score v3

Branch: `v3`

Status: major-version development branch. It is not part of `main` until an
approved release merge is completed.

## What This Branch Does

V3 turns the portfolio area into a Pro and institutional research surface. It
contains the complete V2.2 factor-research work plus expanded portfolio
simulation, benchmark, exposure, concentration, risk, attribution, income and
tax-estimate tools.

Basic users retain the regular two-year Monte Carlo view. Pro/internal users
receive the advanced Monte Carlo view and institutional analytics. Access is
selected by the existing user-plan flag; the two views are not shown together.

## Implemented Portfolio Features

- Benchmark selection for `SPY`, `QQQ`, `IWM`, `DIA`, `VTI` and `ACWI`.
- Benchmark-aware backtests, portfolio comparisons, Monte Carlo projections
  and weak-link analysis. `SPY` remains the default.
- Pro Monte Carlo models: geometric Brownian motion, bootstrap, fat-tail and
  regime-aware simulation, including portfolio and benchmark ranges/medians.
- Sector, industry, country, market-cap and style exposure estimates.
- Estimated liquidity, hidden concentration, correlation matrix,
  correlation-threshold clustering and PCA concentration summary.
- Holding-level risk budgets, historical stress tests, scenario shocks and
  policy-limit checks.
- Portfolio factor exposure, holding return attribution and rolling
  attribution.
- Rebalancing suggestions, estimated portfolio income/yield and a simplified
  unrealized gain/loss tax view.
- Navigation fixes that preserve the portfolio tab and direct links.

The institutional calculations are implemented in
`codes/engine/institutional_portfolio.py`. They are research estimates based on
the holdings and histories available to the application; they are not orders,
tax advice or a substitute for an execution/risk platform.

## Included Factor Research

The Analyze page also includes CAPM, Fama-French 3 Factor, Fama-French 5 Factor
and Carhart 4 Factor models, plus holding, return and rolling attribution.
Older analysis snapshots can be backfilled at view time when sufficient stock,
benchmark and factor history is available.

## Data and Compatibility

- Uses existing portfolio holdings, cached company analysis, public price
  history, benchmark history and the factor-return provider.
- Institutional analytics are calculated for the request and are not written
  to JSON files.
- Existing `spy_*` result fields remain as compatibility aliases.
- Existing users do not need to rerun company analyses solely to expose the
  added portfolio or factor views.
- Missing source inputs produce unavailable/limited outputs rather than
  fabricated values.

Full option-chain analytics, bonds, execution quality, complete dividend
forecasts and full tax-lot accounting are not implemented here. They remain
Track D work because production-grade versions can require licensed data.

## Run and Verify

Use the normal application setup and launch command for this repository. Open
the Portfolio tab after creating a portfolio and adding holdings. The advanced
surface requires a user whose plan resolves to Pro/internal access.

Run the focused branch tests with:

```bash
PYTHONPATH=. pytest -q \
  tests/test_v3_institutional_portfolio.py \
  tests/test_v22_factor_research.py \
  tests/test_v22_analyze_integration.py \
  tests/test_issue_034_navigation_direct_link.py
```

Detailed reusable publishing notes are in `RELEASE_NOTES.md`.
