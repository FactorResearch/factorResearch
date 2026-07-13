# Graham Score v2.1

Branch: `v2.1`

Status: risk-analytics release branch. It remains independent from `main`
until an approved release merge.

## What This Branch Does

V2.1 adds company distress models to Analyze and downside/risk analytics to the
portfolio workflow. It uses existing normalized financial statements and
historical return series; it does not require a premium market-data feed.

## Company Distress Models

- Ohlson O-Score with probability and interpretation.
- Zmijewski Score with probability and interpretation.
- Altman distress output integrated into the same Analyze risk presentation.

The implementations live in `codes/models/distress_scores.py`. Models return
unavailable status when required financial inputs are absent instead of
substituting fabricated values.

## Portfolio and Return Risk

- Maximum drawdown and portfolio maximum drawdown.
- Downside deviation, historical VaR and CVaR.
- Recovery time, Recovery Factor and drawdown curve data.
- Underwater chart data.
- Worst month, quarter and year.
- Ulcer Index.
- Rolling Sharpe and rolling Sortino series.

Portfolio risk calculations live in
`codes/models/portfolio_risk_analytics.py` and are exposed in the Portfolio
interface. Results describe observed historical behavior; they are not a
forecast or a trading instruction.

## Data and Compatibility

- Uses financial inputs already loaded by company analysis and price history
  already used by portfolio analytics.
- Does not create a separate JSON dataset or require users to repopulate a new
  database.
- Missing or insufficient observations produce explicit unavailable output.
- Includes chart-cache support and compatibility for legacy cached analysis
  records.

## Scope Boundaries

This branch does not include V2.2 factor regressions, V3 institutional
portfolio analytics, advanced Monte Carlo models or option-chain analytics.
VaR/CVaR are historical estimates and do not represent guaranteed loss limits.

## Run and Verify

Use the normal application startup. Company distress results appear in Analyze
when the required statement fields exist. Portfolio risk sections appear after
a portfolio has enough holdings and historical observations for calculation.

Run focused tests with:

```bash
PYTHONPATH=. pytest -q \
  tests/test_v21_risk_analytics.py \
  tests/test_issue_041_chart_caching.py
```
