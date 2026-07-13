# Release Notes

Last updated: 2026-07-13

These notes are organized by branch so they can be reused for publishing,
launch posts, upgrade emails and internal release checklists.

## `v3` — Institutional Portfolio Analytics

Formerly developed as `v2.3`, promoted to a major version because the portfolio
surface became a full Pro/institutional release.

### User-Facing Highlights

- Added V3 institutional portfolio analytics for Pro/internal users.
- Added benchmark selection for portfolio analysis: `SPY`, `QQQ`, `IWM`,
  `DIA`, `VTI` and `ACWI`.
- Made portfolio backtests, Monte Carlo projections, comparison views and
  weak-link analysis benchmark-aware.
- Kept the regular Monte Carlo chart for basic users.
- Added Pro Monte Carlo using advanced models:
  - GBM
  - Bootstrap
  - Fat-tail
  - Regime-aware
- Kept benchmark projected range and median visible in the Pro Monte Carlo
  chart.
- Added portfolio exposure analysis:
  - Sector
  - Industry
  - Country
  - Market cap
  - Style
- Added institutional concentration diagnostics:
  - Estimated liquidity
  - Hidden concentration detection
  - Correlation matrix
  - Hierarchical clustering
  - PCA summary
- Added Pro portfolio decision tools:
  - Risk budgeting by holding
  - Scenario shocks
  - Risk limit / policy checks
  - Portfolio factor exposure
  - Return attribution
  - Rolling attribution
  - Rebalancing suggestions
  - Income/yield estimate
  - Tax-aware unrealized gain/loss estimate

### Compatibility Notes

- Default benchmark remains `SPY`.
- Existing `spy_*` fields are preserved as compatibility aliases.
- Users do not need to rerun old analyses just to see the new portfolio
  features.
- New institutional analytics are request-scoped and not saved as JSON.

### Data Notes

- V3 uses existing holdings, cached company analysis, public price history and
  benchmark history.
- No licensed premium feed is required for the V3 portfolio analytics included
  in this release.
- Full options, bond, execution-quality, complete dividend forecast and full
  tax-lot functionality remain deferred to Track D.

## `v2.2` — Factor Research

### User-Facing Highlights

- Added V2.2 factor research to Analyze.
- Added calculated factor models:
  - CAPM
  - Fama-French 3 Factor
  - Fama-French 5 Factor
  - Carhart 4 Factor
- Added attribution surfaces:
  - Holdings attribution
  - Return attribution
  - Rolling attribution
- Added backfill support so older analysis pages can show V2.2 factor research
  when enough stock and benchmark history is available.
- Improved factor model grid readability.

### Compatibility Notes

- V2.2 views are backward compatible with existing analysis snapshots.
- Missing factor datasets are handled as unavailable data, not fake
  placeholder output.

## `v2.1` — Risk Analytics

### User-Facing Highlights

- Added risk analytics branch covering distress and downside risk work.
- Added company risk models from the roadmap:
  - Ohlson O-Score
  - Zmijewski Score
  - Altman integration
- Added portfolio and return-risk concepts from the roadmap:
  - Maximum drawdown
  - Portfolio maximum drawdown
  - Portfolio downside deviation
  - VaR
  - CVaR
  - Recovery time
  - Drawdown curve
  - Underwater chart
  - Worst month / quarter / year
  - Recovery Factor
  - Ulcer Index
  - Rolling Sharpe
  - Rolling Sortino

### Compatibility Notes

- Chart cache compatibility fixes were included on this branch.

## `v2.0` — Portfolio Optimization

### User-Facing Highlights

- Added portfolio optimization branch from Track A.
- Added optimization models:
  - Mean-Variance Optimizer
  - Maximum Sharpe
  - Minimum Variance
  - Risk Parity
- Added chart cache support and legacy analysis cache compatibility fixes.

### Compatibility Notes

- There are two local branch names, `v2.0` and `V2.0`. Treat lowercase `v2.0`
  as the canonical release branch unless this is intentionally changed later.

## `option-chain` — Options Signal Work

Status: work-in-progress branch, not a core release branch yet.

### User-Facing Highlights

- Adds an option chain signal engine foundation.
- This work belongs under Track D before public release because production
  option chains, Greeks, IV Rank, IV Percentile and volatility surface data
  require premium/licensed data feeds.

## `new-layout` — Layout Work

Status: work-in-progress branch, not a core release branch yet.

### User-Facing Highlights

- Adds layout changes from the `new-layout` branch.
- Includes chart cache support and legacy analysis cache compatibility fixes.

## `main`

Status: stable base branch.

Use `main` as the merge target for approved release branches.
