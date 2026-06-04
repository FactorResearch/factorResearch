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
