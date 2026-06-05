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

Purpose:

Earnings estimate revisions are among the most consistently documented predictors of future stock outperformance.

Potential composite weight:

* 8–12%

Dependencies:

* Market data provider
* Analyst estimate data

---

## P1 — Profitability Model

### profitability.py

Priority: P1

Expected Impact: Very High

Responsibilities:

* Economic profitability analysis
* Return quality assessment
* Margin durability evaluation

Key metrics:

* ROIC
* ROA
* Gross Profit / Assets
* Operating Margin Stability
* ROIC Persistence

Purpose:

Capture persistent profitability factors not fully represented by Graham, Piotroski, or Altman.

Potential composite weight:

* 5–10%

Dependencies:

* Income statement
* Balance sheet

---

## P1 — Free Cash Flow Quality Model

### fcf_quality.py

Priority: P1

Expected Impact: Very High

Responsibilities:

* Cash flow quality analysis
* Earnings-to-cash conversion analysis
* Free cash flow consistency scoring

Key metrics:

* FCF Margin
* FCF Conversion Ratio
* FCF Growth
* FCF Stability

Purpose:

Reduce exposure to accounting-driven earnings and value traps.

Potential composite weight:

* 5–10%

Dependencies:

* Cash flow statements
* Income statements

---

## P2 — Capital Allocation Model

### capital_allocation.py

Priority: P2

Expected Impact: High

Responsibilities:

* Management capital allocation analysis
* Shareholder return assessment
* Buyback efficiency evaluation

Key metrics:

* Shareholder Yield
* Buyback Yield
* Dilution Rate
* Debt Growth vs Revenue Growth
* Capital Return Ratio

Purpose:

Identify management teams that consistently create shareholder value.

Potential composite weight:

* 5–10%

Dependencies:

* Share count history
* Dividend history
* Debt history

---

## P2 — Growth Quality Model

### growth_quality.py

Priority: P2

Expected Impact: High

Responsibilities:

* Sustainable growth evaluation
* Efficient growth scoring
* Growth durability analysis

Key metrics:

* Revenue CAGR
* EPS CAGR
* FCF CAGR
* ROIC Trend
* Margin Expansion

Purpose:

Reward efficient growth while avoiding speculative growth.

Potential composite weight:

* 5–10%

Dependencies:

* Historical financial statements

---

## P3 — Market Regime Model

### regime.py

Priority: P3

Expected Impact: Moderate to High

Responsibilities:

* Market condition classification
* Dynamic factor weighting
* Risk-on / risk-off detection

Key metrics:

* SPY 200-Day Moving Average
* Market Breadth
* Volatility Regime
* Trend Strength

Regimes:

* Bull
* Neutral
* Bear

Purpose:

Adjust factor exposure dynamically based on market conditions.

Example:

Bull Market:

* Momentum ↑
* Growth ↑

Bear Market:

* Quality ↑
* Risk Controls ↑

Dependencies:

* Market data
* Volatility metrics

---

## P4 — Advanced Research Modules

Potential future research candidates:

### insider_activity.py

Priority: P4

Key metrics:

* Insider purchases
* Executive buying activity
* Ownership changes

---

### factor_momentum.py

Priority: P4

Key metrics:

* Value factor strength
* Momentum factor strength
* Quality factor strength

Purpose:

Dynamically rotate between factor exposures.

---

### alternative_data.py

Priority: P4

Key metrics:

* Sentiment
* News flow
* Social signals

Purpose:

Experimental alpha generation.

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

---

# Long-Term Composite Target

Current Factors:

* Graham
* Buffett
* Quality
* Momentum
* Piotroski
* Risk
* Altman

Future Factors:

* Value
* Quality
* Momentum
* Financial Strength
* Profitability
* Free Cash Flow Quality
* Earnings Revisions
* Capital Allocation
* Growth Quality
* Dynamic Regime Adjustments

Goal:

Improve excess return generation while reducing factor overlap and improving robustness across market cycles.
