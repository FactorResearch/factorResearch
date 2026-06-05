# PROJECT_MAP.md

## Project Purpose

Fundamental stock analysis and portfolio analytics platform.

The repository evaluates companies using multiple value-investing frameworks and portfolio risk models.

---

# Directory Ownership

## Data Acquisition Layer

### sec_data.py

Responsibilities:

* SEC/market data retrieval
* Financial statement collection
* Dividend history retrieval
* Historical company fundamentals

Key outputs:

* Financial statements
* Dividend records
* Company metrics

Dependencies:

* Used by scoring models
* Used by portfolio analytics

---

## Value Investing Models

### graham.py

Responsibilities:

* Benjamin Graham screening
* Earnings stability
* Dividend history analysis
* Financial strength checks

Key metrics:

* Consecutive dividend years
* Earnings consistency
* Graham score

Dependencies:

* sec_data.py

---

### piotroski.py

Responsibilities:

* Piotroski F-Score calculation

Key metrics:

* Profitability
* Leverage
* Liquidity
* Operating efficiency

Dependencies:

* Financial statements
* Historical fiscal periods

---

### altman.py

Responsibilities:

* Altman Z-Score

Key metrics:

* Working capital ratio
* Retained earnings ratio
* EBIT ratio
* Market value ratio
* Asset turnover ratio

Dependencies:

* Balance sheet
* Income statement
* Market capitalization

---

### greenblatt.py

Responsibilities:

* Magic Formula ranking

Key metrics:

* Earnings Yield
* Return on Capital
* Net Working Capital

Dependencies:

* Financial statements
* Enterprise value calculations

---

## Composite Scoring

### scorer.py

Responsibilities:

* Aggregates individual model outputs
* Produces composite ranking scores
* Weighting and normalization

Dependencies:

* graham.py
* piotroski.py
* altman.py
* greenblatt.py

---

### app.py

Responsibilities:

* User-facing score presentation
* Dashboard output
* Ranking display
* Final composite score display

Dependencies:

* scorer.py

---

## Portfolio Analytics

### portfolio.py

Responsibilities:

* Portfolio simulation
* Monte Carlo projections
* Portfolio volatility
* Portfolio return estimation

Key concepts:

* Covariance matrix
* Correlation adjustments
* Geometric return assumptions

Dependencies:

* Historical return series

---

### risk_metrics.py

Responsibilities:

* Risk calculations

Metrics:

* Sharpe Ratio
* Sortino Ratio
* Maximum Drawdown
* Volatility

Dependencies:

* Historical return series

---

# Current Audit Priorities

1. Dividend history lookback
2. Consecutive dividend year logic
3. Covariance-based portfolio volatility
4. Geometric Monte Carlo drift
5. Proper YoY Piotroski comparisons
6. Partial Altman scaling
7. Greenblatt NWC cash exclusion
8. Composite score EY decision
9. Sortino denominator correction

---

# Rules For AI Agents

When working on a task:

1. Read only relevant files.
2. Avoid repository-wide scans.
3. Avoid unrelated refactors.
4. Preserve public APIs.
5. Add tests for all changes.
6. Produce minimal diffs.
7. Stop after completing requested scope.

---
# Future Model Improvements

The following enhancements are candidates for future development after current audit priorities are complete.

Priority definitions:

* P1 = Highest expected impact on stock selection performance
* P2 = High impact and strong complementary factor
* P3 = Moderate impact / portfolio enhancement
* P4 = Advanced optimization

---

## P1 — Earnings Revision Model

### earnings_revision.py

Priority: P1

Expected Impact: Very High

Responsibilities:

* Analyst EPS revision tracking
* Revenue estimate revision tracking
* Earnings surprise analysis
* Forward estimate momentum

Key metrics:

* 30-day EPS revision %
* 90-day EPS revision %
* Revenue revision %
* Earnings surprise %

---

## P1 — Profitability Model

### profitability.py

Priority: P1

Expected Impact: Very High

---

## P1 — Free Cash Flow Quality Model

### fcf_quality.py

Priority: P1

Expected Impact: Very High

---

## P2 — Capital Allocation Model

### capital_allocation.py

Priority: P2

Expected Impact: High

---

## P2 — Growth Quality Model

### growth_quality.py

Priority: P2

Expected Impact: High

---

## P3 — Market Regime Model

### regime.py

Priority: P3

Expected Impact: Moderate to High

---

## P4 — Advanced Research Modules

### insider_activity.py

### factor_momentum.py

### alternative_data.py

Priority: P4


---

## P5 — Options Trading Intelligence Layer

### options_signal_engine.py

Priority: P4

Expected Impact: High (tactical alpha / derivatives layer)

### Responsibilities:

* CALL vs PUT directional prediction
* Short-term option price movement modeling (not expiry outcome)
* Strike + expiry optimization
* IV regime + volatility expansion detection
* Options flow anomaly detection
* Risk-adjusted edge scoring for derivatives trades

### Key Outputs:

* Directional bias (CALL / PUT)
* Probability option price increases (P_up)
* Expected short-horizon return
* Recommended strike / expiry pair
* Risk score (theta + IV + liquidity)
* Edge score (alpha strength)

### Core Design Principle:

> Models option mark-to-market movement, not expiration payoff

### Dependencies:

* sec_data.py
* regime.py
* risk_metrics.py
* portfolio.py

---
# Recommended Development Order

1. profitability.py
2. fcf_quality.py
3. earnings_revision.py
4. capital_allocation.py
5. growth_quality.py
6. regime.py
7. insider_activity.py
8. factor_momentum.py
9. alternative_data.py
10. options_signal_engine.py

---

# READJUSTED COMPOSITE WEIGHTING (PROPOSED)

After adding the new modules, the scoring system should evolve from overlapping legacy factors into a more orthogonal structure.

## Current Model

* Graham — 15%
* Buffett — 25%
* Quality — 18%
* Momentum — 14%
* Piotroski — 14%
* Risk — 8%
* Altman — 6%

Total: 100%

---

## Proposed Adjusted Model

To reduce overlap and improve signal independence:

### Core Factors

* Value (Graham + Greenblatt) — 12%
* Quality (Buffett + Piotroski partial overlap reduced) — 18%
* Momentum — 12%
* Risk — 6%

### New Alpha Factors

* Profitability (ROIC-based) — 12%
* Free Cash Flow Quality — 10%
* Earnings Revisions — 12%
* Capital Allocation — 8%
* Growth Quality — 7%

### Stability / Safety Layer

* Altman Z-Score — 3%

---

## Final Adjusted Allocation

| Factor             | Weight |
| ------------------ | ------ |
| Value              | 12%    |
| Quality            | 18%    |
| Momentum           | 12%    |
| Profitability      | 12%    |
| FCF Quality        | 10%    |
| Earnings Revisions | 12%    |
| Capital Allocation | 8%     |
| Growth Quality     | 7%     |
| Risk               | 6%     |
| Altman Z           | 3%     |

**Total: 100%**

---

## Key Structural Change

This new weighting improves the model by:

* Reducing redundancy between Graham / Buffett / Piotroski / Altman
* Increasing exposure to forward-looking signals (earnings revisions)
* Introducing cash-flow based validation (FCF quality)
* Separating profitability from generic “quality”
* Making the system more orthogonal and less correlated

---

## Expected Impact

If implemented with clean data pipelines and proper backtesting:

* Higher Sharpe ratio potential
* Reduced drawdowns in value traps
* Better cyclical adaptability
* Improved SPY-relative consistency
