# Cenvarn— Scoring Methodology

> **Auditable. Deterministic. No black boxes.**
>
> Every score this app produces can be traced back to a public SEC EDGAR filing and a documented formula. This page is that documentation.

All fundamental data is sourced exclusively from **SEC EDGAR XBRL filings** (free, public API — no vendor dependency). Price data comes from Finnhub → Tiingo → Alpha Vantage in priority order. No analyst estimates are required to produce a composite score.

---

## Table of Contents

1. [Composite Score — Enhanced Orthogonal Model](#1-composite-score--enhanced-orthogonal-model)
2. [Graham — Intrinsic Value Estimate](#2-graham--intrinsic-value-estimate)
3. [Buffett — Economic Moat Rating](#3-buffett--economic-moat-rating)
4. [Piotroski F-Score — Financial Health](#4-piotroski-f-score--financial-health)
5. [Altman Z-Score — Bankruptcy Risk](#5-altman-z-score--bankruptcy-risk)
6. [Quality — Business Quality](#6-quality--business-quality)
7. [Momentum — Price Trend](#7-momentum--price-trend)
8. [Risk Metrics — Risk-Adjusted Profile](#8-risk-metrics--risk-adjusted-profile)
9. [Profitability — Structural Profitability](#9-profitability--structural-profitability)
10. [FCF Quality — Cash Generation Quality](#10-fcf-quality--cash-generation-quality)
11. [Capital Allocation — Management Quality](#11-capital-allocation--management-quality)
12. [Growth Quality — Long-Term Growth](#12-growth-quality--long-term-growth)
13. [Earnings Revision — Forward Momentum](#13-earnings-revision--forward-momentum)
14. [Factor Momentum — Price + Fundamental Trend](#14-factor-momentum--price--fundamental-trend)
15. [Greenblatt — Magic Formula Ranking](#15-greenblatt--magic-formula-ranking)
16. [Regime — Market Condition Overlay](#16-regime--market-condition-overlay)
17. [Insider Activity — Management Conviction](#17-insider-activity--management-conviction)
18. [Alternative Data — Phase E Signals](#18-alternative-data--phase-e-signals)

---

## 1. Composite Score — Enhanced Orthogonal Model

The final score is a **weighted average of 10 independent factors**, each normalised to 0–100. Factors are chosen to be as orthogonal (non-overlapping) as possible.

### Weights

| Factor | Weight | Source |
|--------|--------|--------|
| Quality | 18% | `quality.py` |
| Graham / Value | 10% | `graham.py`  |
| Momentum | 10% | `momentum.py` |
| Profitability | 12% | `profitability.py` |
| Earnings Revision | 12% | `earnings_revision.py` |
| FCF Quality | 10% | `fcf_quality.py` |
| Capital Allocation | 8% | `capital_allocation.py` |
| Growth Quality | 9% | `growth_quality.py` |
| Risk | 8% | `risk_metrics.py` |
| Altman Safety | 3% | `altman.py` |
| **Total** | **100%** | |

*Co-momentum shifts 2% from Momentum to Risk; the regime layer absorbs the crowding signal.*

### Formula

```
composite = Σ (pillar_pct × weight)
```

Each `pillar_pct` is the model's raw score divided by its maximum, converted to a 0–100 percentage.

### Hard Caps

| Condition | Effect |
|-----------|--------|
| Altman **Distress Zone** | Score capped at **50/100** |
| Altman **Grey Zone** | Score reduced by **10 points** |
| Both Graham MoS < 0 AND Buffett MoS < 0 | Score capped at **44.9** (CAUTION band) |
| Either Graham MoS < 0 OR Buffett MoS < 0 | Score capped at **59.9** (BALANCED band) |

### Verdict Thresholds

| Score | Verdict |
|-------|---------|
| ≥ 75 | HIGH CONVICTION |
| ≥ 60 | FAVORABLE |
| ≥ 45 | BALANCED |
| ≥ 30 | CAUTION |
| < 30 | UNFAVORABLE |

---

## 2. Graham — Intrinsic Value Estimate

**Maximum: 100 points.** Based on Benjamin Graham's *The Intelligent Investor* criteria for defensive investors.

### Criteria

| # | Criterion | Requirement | Points |
|---|-----------|-------------|--------|
| 1 | Price-to-Earnings | ≤ 15× | 15 |
| 2 | Price-to-Book | ≤ 1.5× | 10 |
| 3 | P/E × P/B Combined | ≤ 22.5 | 5 |
| 4 | **Intrinsic Value & Margin of Safety** | Price ≤ 67% of GN | 20 |
| 5 | Current Ratio | ≥ 2.0× | 10 |
| 6 | Long-Term Debt / Equity | ≤ 1.0× | 10 |
| 7 | EPS Stability & Growth | ≥ 33% growth, no loss years | 15 |
| 8 | Dividend Track Record | 20+ consecutive years | 10 |
| 9 | Net-Net Working Capital | NNWC > Market Cap | 5 |

### Key Formula — Graham Number

The Graham Number is the geometric mean of earnings-based and book-value-based intrinsic value:

```
Graham Number = √(22.5 × EPS × BVPS)
```

Where:
- `EPS` = trailing 12-month earnings per share (from SEC net income ÷ shares outstanding)
- `BVPS` = book value per share (stockholders' equity ÷ shares outstanding)
- `22.5` = Graham's combined ceiling: 15× P/E × 1.5× P/B

**Margin of Safety** = `(Graham Number − Price) / Graham Number × 100`

Positive = price is below intrinsic value. Negative = overvalued.

### P/E Scoring Detail

| P/E | Score |
|-----|-------|
| ≤ 15× | 15 pts (full) |
| ≤ 20× | 8 pts (partial) |
| > 20× | 0 pts |

### Dividend Counting Rule

Only **consecutive** uninterrupted years of positive dividends are counted. A gap in payments resets the streak. A company paying dividends from 2000–2015 then stopping gets 0 years, not 15.

---

## 3. Buffett — Economic Moat Rating

**Maximum: 100 points.** Based on Warren Buffett's published criteria from Berkshire Hathaway annual letters and *The Warren Buffett Way* (Hagstrom, 2013).

### Criteria

| # | Criterion | Requirement | Points |
|---|-----------|-------------|--------|
| 1 | Consistent ROE ≥ 15% | 5+ consecutive years | 20 |
| 2 | Debt-to-Earnings (payback) | Net debt repayable < 3yr of NI | 10 |
| 3 | Net Profit Margin | ≥ 10%, stable | 15 |
| 4 | EPS Growth (7yr CAGR) | ≥ 7%/yr | 15 |
| 5 | Owner Earnings (FCF) | Positive & growing | 15 |
| 6 | Return on Invested Capital | ≥ 12% | 10 |
| 7 | **Intrinsic Value vs Price (DCF)** | Price ≤ 80% of DCF IV | 15 |

### Key Formula — Two-Stage DCF

Buffett's intrinsic value uses discounted cash flow on **owner earnings per share**:

```
Owner Earnings ≈ Operating Cash Flow − CapEx

Stage 1 (10 years):
  PV₁ = Σ (OE_ps × (1 + g)^t) / (1 + r)^t   for t = 1..10

Stage 2 (terminal value):
  Terminal CF = OE_ps × (1 + g)^10 × (1 + g_terminal)
  PV₂ = Terminal CF / (r − g_terminal) / (1 + r)^10

Intrinsic Value = PV₁ + PV₂
```

Parameters:
- `r` = 12% discount rate (Buffett's stated minimum hurdle)
- `g` = historical EPS CAGR, capped at 15%
- `g_terminal` = 3% (≈ nominal GDP long-term growth)
- `OE_ps` = FCF per share (falls back to EPS if FCF/share is unavailable)

**Plausibility guard:** If FCF/share exceeds 50× the current price, the shares figure is likely contaminated by LP/OP unit counts from REIT co-filings. The model falls back to EPS in this case.

### Moat Grades

| Score | Grade | Label |
|-------|-------|-------|
| ≥ 75 | A | Wide Moat |
| ≥ 55 | B | Narrow Moat |
| ≥ 35 | C | No Clear Moat |
| < 35 | D | Avoid |

---

## 4. Piotroski F-Score — Financial Health

**Maximum: 9 points** (9 binary signals, 1 point each). Based on *Piotroski (2000) "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers,"* Journal of Accounting Research.

High-F-Score value stocks (8–9) outperformed Low-F-Score stocks (0–2) by **7.5%/yr** over 20 years in the original study.

### The 9 Signals

**Profitability (4 signals)**

| Signal | Test | Formula |
|--------|------|---------|
| F1 | ROA > 0 | `Net Income / Total Assets > 0` |
| F2 | Positive Operating Cash Flow | `OCF > 0` |
| F3 | Improving ROA | `ROA_current > ROA_prior` |
| F4 | Quality Earnings (low accruals) | `OCF / Assets > ROA` (cash earnings beat accounting earnings) |

**Leverage / Liquidity / Dilution (3 signals)**

| Signal | Test | Formula |
|--------|------|---------|
| F5 | Decreasing Leverage | `LT_Debt/Assets_current < LT_Debt/Assets_prior` |
| F6 | Improving Current Ratio | `CA/CL_current > CA/CL_prior` |
| F7 | No Share Dilution | `Shares_current ≤ Shares_prior × 1.01` |

**Operating Efficiency (2 signals)**

| Signal | Test | Formula |
|--------|------|---------|
| F8 | Improving Gross Margin | `GP/Revenue_current > GP/Revenue_prior` |
| F9 | Improving Asset Turnover | `Revenue/Assets_current > Revenue/Assets_prior` |

### Year-over-Year Comparison Rule

Prior-year values must be from a period **10–14 months before** the current period end date. This ensures full fiscal-year comparisons, not adjacent quarters. If no prior year is found in this window, the model falls back to the second-most-recent filing.

### Interpretation

| F-Score | Label | Meaning |
|---------|-------|---------|
| 8–9 | Strong | High financial health; historically outperforms |
| 5–7 | Neutral | Mixed signals; monitor |
| 0–4 | Weak | Deteriorating fundamentals; avoid |

### Fallback for Sectors Without LT Debt

Banks and insurers often have no long-term debt in the traditional sense. F5 falls back to `Total Liabilities / Total Assets` when `lt_debt` is unavailable.

---

## 5. Altman Z-Score — Bankruptcy Risk

Based on *Altman (1968) "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy,"* Journal of Finance. Predicts bankruptcy 1–2 years in advance with ~72–80% accuracy.

### Two Model Variants

**Original Model** (public manufacturers — used when PP&E > 0):
```
Z = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 1.0·X5
```

**Z'' Model** (non-manufacturers, services, tech — used when PP&E = 0 or absent):
```
Z'' = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4
```

### Components

| Variable | Formula | Measures |
|----------|---------|---------|
| X1 | Working Capital / Total Assets | Short-term liquidity |
| X2 | Retained Earnings / Total Assets | Accumulated profitability |
| X3 | EBIT / Total Assets | Core operating efficiency |
| X4 | Market Cap / Total Liabilities | Leverage buffer |
| X5 | Revenue / Total Assets | Asset efficiency (Original only) |

### Zone Thresholds

| Model | Safe Zone | Grey Zone | Distress Zone |
|-------|-----------|-----------|---------------|
| Original | Z > 2.99 | 1.81 – 2.99 | Z < 1.81 |
| Z'' | Z > 2.60 | 1.10 – 2.60 | Z < 1.10 |

### Partial Score Normalisation

If fewer than all components are available (e.g. no market price → X4 unavailable), the raw weighted sum is divided by the fraction of total weight present:

```
z_score = raw_sum / available_weight_fraction
```

This prevents missing data from artificially depressing the score. The `available_fraction` is logged in the result for transparency. Minimum 3 components are required to produce a score.

---

## 6. Quality — Business Quality

**Maximum: 100 points.** Pure fundamentals — no price needed.

### Criteria

| # | Criterion | Requirement | Points |
|---|-----------|-------------|--------|
| 1 | Return on Equity | ≥ 15% | 25 |
| 2 | EPS Growth Consistency | Up 4 of last 5 years | 20 |
| 3 | Operating Margin | ≥ 15% | 20 |
| 4 | Free Cash Flow | Positive | 20 |
| 5 | Revenue Growth (5yr) | Positive over 5 years | 15 |

### ROE Scoring

```
ROE = Net Income / Shareholders' Equity × 100
```

| ROE | Score |
|-----|-------|
| ≥ 20% | 25 pts |
| ≥ 15% | 18 pts |
| ≥ 10% | 10 pts |
| < 10% | 0 pts |

### FCF Formula

```
FCF = Operating Cash Flow − abs(CapEx)
FCF Margin = FCF / Revenue × 100
```

| FCF Margin | Score |
|------------|-------|
| ≥ 15% | 20 pts |
| ≥ 8% | 13 pts |
| Positive | 7 pts |
| Negative | 0 pts |

---

## 7. Momentum — Price Trend

**Maximum: 100 points.** Uses monthly price history (resampled from daily data).

### Criteria

| # | Criterion | Requirement | Points |
|---|-----------|-------------|--------|
| 1 | 200-Day Moving Average | Price > MA | 30 |
| 2 | 12-Month Return | > 0% | 30 |
| 3 | Relative Strength vs SPY | Outperforming SPY 12mo | 25 |
| 4 | 3-Month Drawdown | Not down > 20% | 15 |

**Note:** Monthly bars are used throughout. 200D MA ≈ 10 monthly bars. 12M return = price 12 bars ago vs. today.

### 12-Month Return Scoring

| Return | Score |
|--------|-------|
| ≥ 20% | 30 pts |
| ≥ 10% | 20 pts |
| ≥ 0% | 10 pts |
| < 0% | 0 pts |

### Relative Strength (vs SPY)

```
Alpha = Stock_12M_Return − SPY_12M_Return
```

| Alpha | Score |
|-------|-------|
| ≥ +10% | 25 pts |
| ≥ 0% | 15 pts |
| ≥ −10% | 5 pts |
| < −10% | 0 pts |

### 3-Month Drawdown Scoring

| 3M Return | Score |
|-----------|-------|
| ≥ 0% | 15 pts |
| ≥ −10% | 8 pts |
| ≥ −20% | 3 pts |
| < −20% | 0 pts |

---

## 8. Risk Metrics — Risk-Adjusted Profile

**Maximum: 100 points** (for composite integration). Uses monthly log-returns.

### Metrics Computed

| Metric | Formula |
|--------|---------|
| Annual Volatility | `σ_monthly × √12` |
| Sharpe Ratio | `(R_annual − R_f) / σ_annual` where R_f = 4.5% |
| Sortino Ratio | `(R_annual − R_f) / downside_deviation` |
| Beta | `Cov(stock, SPY) / Var(SPY)` |
| Alpha | `R_annual − [R_f + β × (R_SPY − R_f)]` (Jensen's α) |
| Max Drawdown | Peak-to-trough percentage over full history |
| Calmar Ratio | `R_annual / |Max Drawdown|` |
| VaR 95% | 5th percentile monthly log-return |
| CVaR 95% | Mean of returns below VaR threshold |

**Sortino downside deviation** uses total N as denominator (not downside observations only), consistent with Sortino & Price (1994):
```
DD = √( Σ min(0, r_t − R_f)² / N )
```

### Risk Score Breakdown (100 pts total)

| Component | Max Points |
|-----------|------------|
| Sharpe Ratio | 35 |
| Max Drawdown | 30 |
| Annualised Volatility | 20 |
| Beta vs Market | 15 |

| Sharpe | Score |
|--------|-------|
| ≥ 1.5 | 35 pts |
| ≥ 1.0 | 26 pts |
| ≥ 0.5 | 16 pts |
| ≥ 0 | 6 pts |
| < 0 | 0 pts |

---

## 9. Profitability — Structural Profitability

**Maximum: 100 points.** Measures structural business quality using ROIC and margins.

### Component Weights

| Component | Weight |
|-----------|--------|
| ROIC | 35% |
| Gross Profitability (Novy-Marx) | 20% |
| Operating Margin Stability | 15% |
| Capital Efficiency (Asset Turnover) | 15% |
| Incremental ROIC | 15% |

### Key Formulas

**ROIC:**
```
NOPAT = Operating Income × (1 − effective_tax_rate)
IC = Equity + max(LT_Debt − Cash, 0)
ROIC = NOPAT / IC × 100
```

Tax rate is estimated from `1 − Net Income / Operating Income`, capped at 50%. Falls back to 21% corporate rate when data is sparse.

**Novy-Marx Gross Profitability** (2013):
```
Gross Profitability = Gross Profit / Total Assets
```

Higher ratio = superior pricing power and efficiency. Empirically associated with future outperformance even among value stocks.

**Incremental ROIC:**
```
Incremental ROIC = ΔNOPAT / ΔIC   (between current and prior year)
```

Measures the return on *new* capital deployed — a better predictor of future value creation than static ROIC.

### Signal Thresholds

| Score | Signal |
|-------|--------|
| ≥ 80 | STRONG_HIGH_QUALITY |
| ≥ 65 | HIGH_QUALITY |
| ≥ 45 | NEUTRAL |
| ≥ 30 | LOW_QUALITY |
| < 30 | VALUE_TRAP_RISK |

### Normalisation

| ROIC | Normalised Score |
|------|-----------------|
| ≥ 25% | 100 |
| 0–25% | Linear interpolation |
| ≤ 0% | 0 |

| Asset Turnover | Normalised Score |
|----------------|-----------------|
| ≥ 1.0× | 100 |
| 0.1–1.0× | Linear |
| ≤ 0.1× | 0 |

---

## 10. FCF Quality — Cash Generation Quality

**Maximum: 100 points.** Measures earnings quality using up to 10 years of cash flow history.

### Component Weights

| Component | Weight |
|-----------|--------|
| FCF Margin | 25% |
| FCF Conversion | 25% |
| FCF Stability (CV) | 20% |
| FCF Growth Consistency | 15% |
| Accrual Ratio | 15% |

### Key Formulas

```
FCF = Operating Cash Flow − |CapEx|
FCF Margin = FCF / Revenue × 100
FCF Conversion = FCF / Net Income × 100
FCF Stability = std(FCF margins) / |mean(FCF margins)|  [Coefficient of Variation]
FCF CAGR (5yr) = (FCF_now / FCF_5yr_ago)^(1/5) − 1
```

**Sloan Accrual Ratio:**
```
Accrual Ratio = (Net Income − OCF) / avg(Total Assets)
```

Lower (more negative) = higher earnings quality. Cash earnings exceed accounting earnings.

### Normalisation Rules

| FCF Margin | Score |
|------------|-------|
| ≥ 20% | 100 |
| 0–20% | Linear |
| ≤ 0% | 0 |

| Stability CV | Score |
|-------------|-------|
| ≤ 0.20 | 100 (very stable) |
| ≥ 1.00 | 0 (highly volatile) |
| 0.20–1.00 | Linear |

| Accrual Ratio | Score |
|---------------|-------|
| ≤ −0.05 | 100 (excellent) |
| ≥ +0.10 | 0 (low quality) |
| Between | Linear |

### Signal Thresholds

| Score | Signal |
|-------|--------|
| ≥ 80 | STRONG_CASH_GENERATOR |
| ≥ 65 | HIGH_CASH_QUALITY |
| ≥ 45 | NEUTRAL |
| ≥ 30 | WEAK_CASH_QUALITY |
| < 30 | EARNINGS_QUALITY_RISK |

---

## 11. Capital Allocation — Management Quality

**Maximum: 100 points.** Measures how effectively management allocates capital.

### Component Weights

| Component | Weight |
|-----------|--------|
| ROIC Spread (ROIC − 10% hurdle) | 25% |
| Incremental ROIC | 25% |
| Reinvestment Rate | 20% |
| Shareholder Yield | 15% |
| Dilution Rate | 10% |
| Debt Allocation Trend | 5% |

### Key Formulas

**ROIC Spread:**
```
ROIC Spread = ROIC − 10%   (fixed hurdle rate)
```

Positive spread = economic value creation above cost of capital.

**Reinvestment Rate:**
```
Primary:  (CapEx + R&D) / EBIT
Fallback: CapEx / Operating CF
```

**Shareholder Yield:**
```
Buyback Yield = (Shares_prior − Shares_now) / Shares_prior × 100
Dividend Yield = Total Dividends / Market Cap × 100
Shareholder Yield = Buyback Yield + Dividend Yield
```

**Dilution Rate:**
```
Dilution Rate = (Shares_now − Shares_prior) / Shares_prior × 100
```

Negative = buybacks (good). Positive = dilution (bad).

### Reinvestment Rate Scoring (bell-curve)

Optimal range is 20–60% (company reinvesting meaningfully without consuming all earnings):

| Reinvestment Rate | Score |
|-------------------|-------|
| 20–60% (optimal) | 60–100 (peaks at 35%) |
| < 20% | 0–60 (underinvesting) |
| > 60% | 0–60 (overinvesting) |

### Signal Thresholds

| Score | Signal |
|-------|--------|
| ≥ 80 | EXCELLENT_ALLOCATOR |
| ≥ 65 | GOOD_ALLOCATOR |
| ≥ 45 | AVERAGE_ALLOCATOR |
| ≥ 30 | POOR_ALLOCATOR |
| < 30 | CAPITAL_DESTROYER |

---

## 12. Growth Quality — Long-Term Growth

**Maximum: 100 points.** Strict 10-year framework. Requires exactly 10 years of history for each metric; shorter series yield unavailable metrics, which are **reweighted proportionally** (no zero-penalty for missing data).

### Component Weights

| Component | Weight |
|-----------|--------|
| Revenue CAGR (10yr) | 25% |
| EPS CAGR (10yr) | 25% |
| FCF CAGR (10yr) | 20% |
| Margin Stability | 15% |
| Incremental ROIC (10yr) | 15% |

### CAGR Formula

```
CAGR = (End / Start)^(1 / Years) − 1
```

Applied to revenue, EPS, and FCF series. Requires positive start and end values.

### CAGR Normalisation

| CAGR | Normalised Score |
|------|-----------------|
| ≥ 15% | 100 |
| 0% | ~25 |
| −5% | 0 |
| Between | Linear: `(CAGR − (−5%)) / (15% − (−5%)) × 100` |

### Proportional Reweighting

If a metric has insufficient history (< 11 years), its weight is redistributed proportionally to the available metrics:

```
score = Σ(norm_score × weight_k) / available_weight_sum
```

### Signal Thresholds

| Score | Signal |
|-------|--------|
| ≥ 70 | Bullish |
| ≥ 40 | Neutral |
| < 40 | Bearish |

---

## 13. Earnings Revision — Forward Momentum

**Maximum: 100 points.** Empirical basis: stocks with rising EPS estimates outperform those with falling estimates by ~7–10%/yr (Chan, Jegadeesh & Lakonishok, 1996).

### Component Weights

| Component | Weight |
|-----------|--------|
| EPS Revision 30-day proxy | 35% |
| EPS Revision 90-day proxy | 25% |
| Revenue Revision 30-day proxy | 20% |
| Earnings Surprise (4Q avg) | 20% |

### Data Source Dependency

This model requires **Finnhub paid tier** (`eps_estimates`, `revenue_estimates`, `earnings_surprises`, `recommendation_trends`). These methods are absent from the free SDK.

When running on free-tier Finnhub, all four fetchers return empty results and every component defaults to **50/100 (neutral)**. The `n_available` field in the result indicates how many components had real data.

### Scoring Method — Sigmoid

Each component uses a logistic sigmoid rather than a step function, producing smooth scoring across the full range:

```
sigmoid_score = 100 / (1 + e^(−(value − center) / scale))
```

| Component | Center | Scale |
|-----------|--------|-------|
| EPS Revision 30d | 0% | 4% |
| EPS Revision 90d | 0% | 5% |
| Revenue Revision | 0% | 3% |
| Earnings Surprise | +2% | 5% |

Earnings surprise is centred at +2% because companies that beat by 2% are meeting the bar, not exceeding it.

### Signal Thresholds

| Score | Signal |
|-------|--------|
| ≥ 75 | STRONG_UP |
| ≥ 60 | UP |
| ≥ 40 | NEUTRAL |
| ≥ 25 | DOWN |
| < 25 | STRONG_DOWN |

### Revision Proxies (when point-in-time data unavailable)

True point-in-time revision (e.g. Q2-2025 consensus on March 1 vs April 1) requires paid tiers. Two valid proxies are used instead:

1. **Slope of consecutive EPS estimates** across forward periods
2. **Trend in earnings surprise %** (improving beats ⟹ upward revision signal)

Both are empirically correlated with future returns (Standardised Unexpected Earnings literature).

---

## 14. Factor Momentum — Price + Fundamental Trend

**Maximum: 100 points.** Combines short/medium/long-term price momentum with fundamental earnings and ROIC trends.

### Component Weights

| Component | Weight |
|-----------|--------|
| 3-Month Price Return | 20% |
| 6-Month Price Return | 25% |
| 12-Month Price Return | 25% |
| Earnings Momentum (EPS trend slope) | 15% |
| ROIC Trend Slope | 15% |

### Price Return Normalisation

```
norm = clamp((return − (−20%)) / 40%, 0, 1) × 100
```

−20% return → 0. +20% return → 100.

### Earnings Momentum

OLS slope of EPS over up to 5 years, normalised by |mean|:

```
slope = (Σ (i − x̄)(EPS_i − EPS̄)) / Σ (i − x̄)²  /  |EPS̄|  × 100
```

Positive slope = accelerating earnings growth.

### ROIC Trend Slope

Un-normalised OLS slope in **percentage points per year** (not divided by mean, since ROIC is already a ratio):

```
ROIC_slope = OLS_slope(ROIC_series)  [pp/year]
```

Normalisation: −3 pp/yr → 0, +3 pp/yr → 100.

### Signal Thresholds

| Score | Signal |
|-------|--------|
| ≥ 70 | Bullish |
| ≥ 40 | Neutral |
| < 40 | Bearish |

---

## 15. Greenblatt — Magic Formula Ranking

Based on *Greenblatt (2005) "The Little Book That Beats the Market."* Back-tested return: ~30.8%/yr vs ~12.4% for S&P 500 (1988–2004).

**Important:** This model is **cross-sectional only**. A magic_score only becomes meaningful after ranking a stock against a full universe of peers. The raw metrics (earnings yield, ROIC) are stored for display; the `magic_score` is `null` on single-stock analysis.

### Two Metrics

**Earnings Yield:**
```
EV = Market Cap + LT Debt − Cash
Earnings Yield = EBIT / EV   [higher = cheaper]
```

**Return on Invested Capital:**
```
NWC = Current Assets − Cash − Current Liabilities
IC = NWC + Net PP&E  (fallback: Total Assets − Current Liabilities)
ROIC = EBIT / IC   [higher = better business]
```

### Ranking Method

1. Rank all stocks by Earnings Yield descending (rank 1 = cheapest)
2. Rank all stocks by ROIC descending (rank 1 = best business)
3. Magic Score = combined rank: `(EY_rank + ROIC_rank)` — lower combined = better
4. Normalise to 0–100: `(1 − (combined − 2) / (2×N − 2)) × 100`

Only stocks with **positive** earnings yield and ROIC qualify for ranking. Negative EY stocks are excluded.

### Enterprise Value Note

The EV formula (`Market Cap + LT Debt − Cash`) is the **single authoritative implementation** in this codebase, defined in `greenblatt.enterprise_value()`. All other modules that need EV call this function rather than re-implementing it.

---

## 16. Regime — Market Condition Overlay

Not a per-stock factor — a **portfolio-level risk control** applied after composite scoring. Uses **SPY** monthly price history to classify the current market regime.

### Inputs (all from SPY monthly price bars)

| Metric | Monthly-Bar Equivalent |
|--------|----------------------|
| 50-Day MA | 3 monthly bars |
| 200-Day MA | 10 monthly bars |
| 20-Day Volatility | 1 monthly bar |
| 60-Day Volatility | 3 monthly bars |
| 252-Day Peak Lookback | 12 monthly bars |

### Trend Score (0–100)

Three binary signals:
1. SPY price > 200-bar MA (+1)
2. 50-bar MA > 200-bar MA (+1)
3. SPY price > 50-bar MA (+1)

```
Trend Score = (signals / max_possible_signals) × 100
```

### Regime Classification

| Trend Score | Vol Percentile | Regime |
|-------------|---------------|--------|
| ≥ 60 | < 50% | BULL_LOW_VOL |
| ≥ 60 | ≥ 50% | BULL_HIGH_VOL |
| ≤ 40 | < 50% | BEAR_LOW_VOL |
| ≤ 40 | ≥ 50% | BEAR_HIGH_VOL |
| 40–60 | any | SIDEWAYS |

**Crisis override:** if Drawdown ≤ −25% AND Vol Percentile ≥ 90%, regime is forced to CRISIS regardless of trend score.

### Regime Multipliers

| Regime | Score Multiplier | Max Equity Exposure |
|--------|-----------------|---------------------|
| BULL_LOW_VOL | ×1.10 | 100% |
| BULL_HIGH_VOL | ×1.00 | 90% |
| SIDEWAYS | ×0.90 | 90% |
| BEAR_LOW_VOL | ×0.80 | 70% |
| BEAR_HIGH_VOL | ×0.65 | 70% |
| CRISIS | ×0.50 | 40% |

The multiplier scales the final composite score (capped at 100). The max equity exposure governs position sizing overlays.

---

## 17. Insider Activity — Management Conviction

**Maximum: 100 points.** Measures insider trading behaviour.

### Component Weights

| Component | Weight |
|-----------|--------|
| Net Insider Buying | 40% |
| Cluster Buying Score | 40% |
| Insider Type Quality | 20% |

### Net Insider Buying

```
Net Buying = (Buy Volume − Sell Volume) / Shares Outstanding × 100
```

Clipped to [−100%, +100%]. Normalised to [0, 100] by centering at 0:
```
score = clamp(50 + net_buying × 0.5, 0, 100)
```

Only **open-market** transactions (codes P and S from SEC Form 4) are included. Option exercises are excluded unless flagged as open-market.

### Cluster Buying Detection

A cluster is detected when, within a 42-day window:
- ≥ 2 distinct insiders bought
- ≥ 3 total buy transactions
- No single insider accounts for ≥ 80% of cluster buy volume

Cluster score considers: number of insiders, recency-weighted volume (linear decay over 42 days).

### Insider Type Quality

```
HQ_Fraction = Volume bought by CEO/CFO/COO/President/Chairman/Director / Total buy volume
Type_Score = 30 + HQ_Fraction × 70
```

High-seniority insiders (30 → 100 range). Returns 50 (neutral) when no buys exist.

### Signal Thresholds

| Score | Signal |
|-------|--------|
| ≥ 70 | BULLISH |
| ≥ 40 | NEUTRAL |
| < 40 | BEARISH |

### Low Coverage Rule

When only 1 analyst covers the stock (`n_analyst ≤ 1`), revision breadth is set to `null` to avoid signal noise from a single analyst's revisions.

---

## 18. Alternative Data — Phase E Signals

**Display-only.** Alternative Data is not included in the enhanced composite score. It provides provider-ready research signals while preserving deterministic scoring and avoiding hidden black-box dependencies.

### Phase E Scope

- [x] SEC 8-K sentiment analysis (deterministic, auditable, no external AI dependency)
- [x] Hiring velocity via job posting trends
- [x] Web traffic analytics (once a reliable long-term data source is available)
- [x] Insider buying and selling trends
- [x] Institutional ownership changes
- [x] Patent and intellectual property activity
- [x] Supply chain relationship analysis (long-term research)

### Implemented Signals

SEC 8-K sentiment, insider buying/selling trends, institutional ownership changes, and patent/IP activity are live when their source data is available:

- SEC 8-K sentiment uses recent SEC EDGAR 8-K / 8-K/A primary documents.
- Insider buying/selling trends reuse the same open-market Form 4 transaction feed used by the Insider Activity card.
- Institutional ownership changes use Finnhub institutional ownership data, aggregated by quarter.
- Patent/IP activity uses Finnhub USPTO patent data, aggregated by year.

Hiring velocity, web traffic, and supply-chain relationship analysis expose deterministic trend-scoring hooks for future provider data. Until those durable sources are wired in, those signals remain neutral and explicitly marked as planned, waiting for source, or research.

### SEC 8-K Sentiment

Recent 8-K and 8-K/A primary filing documents are fetched from SEC EDGAR, persisted in the `sec_8k_filings` Postgres table by accession number, and scored with a fixed lexicon. The method is deterministic: the same filing text and term dictionary always produce the same score. No external AI model or probabilistic classifier is used.

When no 8-K text is available, the signal is `NO_DATA` and the Alternative Data score remains neutral at `50/100`.

### Provider Trend Signals

When provider trend data is supplied, Phase E compares the latest value with the prior baseline:

```
delta_pct = (latest - prior) / prior × 100
score = clamp(50 + delta_pct × 2, 0, 100)
```

Positive trend acceleration moves the signal above 50; deterioration moves it below 50. Missing or insufficient provider data remains neutral.

---

## Data Lineage

All fundamental data flows as follows:

```
SEC EDGAR /companyfacts/{CIK}.json
         ↓
sec_data.py  (sector-aware XBRL concept selection)
         ↓
sec_facts dict (canonical keys: eps, bvps, revenue, op_income, ...)
         ↓
Individual model files (graham.py, piotroski.py, ...)
         ↓
scorer.py  (weighted composite)
         ↓
app.py  (display)
```

The `sec_facts` dict uses **sector-aware XBRL concept fallback lists**. For example:
- Banks use `InterestAndDividendIncomeOperating` instead of `Revenues` for top-line
- Insurers use `PremiumsEarnedNet` for revenue
- REITs use `RealEstateRevenueNet`

This prevents cross-sector scoring artefacts without any manual data cleaning.

### Cache Invalidation

Rather than time-based TTL, caches are invalidated by **filing date**:
1. Fetch the lightweight `/submissions/` endpoint (~few KB) for the latest 10-K/10-Q date
2. Compare against the cached filing date
3. Re-fetch the heavy `/companyfacts/` blob (~1 MB) only if SEC has a newer filing

This means cached scores remain valid until the company files a new report — no unnecessary API calls, no stale data served after a filing.

---

## Reproducibility

Given the same inputs, **every score is deterministic**. There are no random seeds, ML models, or probabilistic components in any scoring model (Monte Carlo simulations are explicitly labelled and isolated in the portfolio projection engine, not in stock scoring).

To verify any score:
1. Download the company's SEC XBRL data from `https://data.sec.gov/api/xbrl/companyfacts/CIK{N}.json`
2. Apply the formulas documented above
3. The result will match what the app displays

---

*Last updated: 2025. Formulas and weights are version-controlled in this repository.*
