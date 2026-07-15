# Graham Score v2.0

Branch: `v2.0`

Status: canonical V2.0 portfolio-optimization release branch.

## Scope

V2.0 adds long-only portfolio allocation research to the shared application.
Users can compare current allocation with four calculated methods:

- Mean-Variance
- Maximum Sharpe
- Minimum Variance
- Risk Parity

The canonical implementation is `codes/models/portfolio_optimization.py`.
Results include weights, expected annual return, annualized volatility, Sharpe
ratio, and risk contribution. All methods are long-only, weights sum to 100%,
and per-holding bounds are enforced.

## Workflow

- Create, select, and delete saved portfolios.
- Add or remove holdings and update share counts.
- Run existing backtest and simulation workflows.
- Run V2.0 optimization from the Portfolio tab.
- Preserve direct Portfolio navigation.

V2.0 uses aligned monthly histories and SciPy. Insufficient history returns
diagnostics and safe fallback output. It does not create executable rebalance
orders or include later V2.1, V2.2, V3, or option-chain features.

## Validation

```bash
PYTHONPATH=. pytest -q \
  tests/test_portfolio_optimization.py \
  tests/test_issue_034_navigation_direct_link.py \
  tests/test_issue_041_chart_caching.py
```

Shared setup, security, and production-proof controls are inherited from
`main`. Keep this published branch synchronized by merging `main`, not rebasing.
