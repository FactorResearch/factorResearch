# Graham Score v2.0

Branch: `v2.0`

Status: canonical V2.0 portfolio-optimization release branch. Do not confuse it
with `v2.0-optimizer-prototype`, which is retained only as an alternate
prototype history.

## What This Branch Does

V2.0 adds long-only portfolio allocation research to the existing Portfolio
workflow. A user can run optimization against the holdings in a saved
portfolio and compare the current allocation with four calculated allocation
methods.

## Implemented Optimizers

- Mean-Variance: balances expected return against covariance-based risk.
- Maximum Sharpe: seeks the highest estimated annualized Sharpe ratio.
- Minimum Variance: seeks the lowest estimated portfolio variance.
- Risk Parity: seeks equal percentage risk contribution across holdings.

The canonical implementation is
`codes/models/portfolio_optimization.py`. The Portfolio interface displays
weights, expected annual return, annualized volatility, Sharpe ratio and risk
contribution for the current and optimized allocations.

All methods are long-only, weights sum to 100%, and per-holding bounds are
applied by the optimizer. Results are historical research estimates, not trade
orders or guarantees of future performance.

## Portfolio Workflow

- Create, select and delete saved portfolios.
- Add/remove holdings and update share counts.
- View holdings and portfolio comparison output.
- Run the existing backtest and simulation workflow.
- Run V2.0 optimization from the Portfolio tab.
- Preserve direct navigation to Portfolio rather than redirecting to Screener.

## Data and Compatibility

- Uses aligned monthly return histories for the portfolio's existing symbols.
- Adds SciPy as the numerical solver dependency.
- Does not require a premium data feed or a new JSON dataset.
- Insufficient histories return diagnostics and safe fallback output.
- Includes chart-cache support and legacy analysis-cache compatibility.

## Scope Boundaries

This branch does not contain V2.1 downside-risk surfaces, V2.2 factor research,
V3 institutional portfolio analytics or option-chain analytics. It does not
generate executable rebalance orders.

## Run and Verify

Install the branch requirements, start the application normally, open the
Portfolio tab, select a portfolio with price history, and use the optimization
action.

Run focused tests with:

```bash
PYTHONPATH=. pytest -q \
  tests/test_portfolio_optimization.py \
  tests/test_issue_034_navigation_direct_link.py \
  tests/test_issue_041_chart_caching.py
```
