# Graham Score — Quant Edition

Full quantitative stock screener combining **Graham's defensive investing** with **modern momentum & quality factors**.

**Three Pillars (Weighted):**
- **Graham Value** (40%) — Price/Earnings, Debt/Equity, Margin of Safety
- **Business Quality** (35%) — ROE, Operating Margins, FCF, Revenue Growth
- **Market Momentum** (25%) — Price trend, 12-mo return, Relative Strength vs SPY

**Verdicts:**
- **STRONG BUY** (70+) — All three signals aligned
- **BUY** (55-70) — Mostly positive
- **WATCH** (40-55) — Mixed; monitor
- **HOLD/WEAK** (25-40) — Significant concerns
- **AVOID** (<25) — Fails multiple pillars

---

## Setup (5 minutes)

### Prerequisites
- Python 3.11+ (3.12+ recommended)
- pip (comes with Python)

### 1. Create Project
```bash
mkdir ~/graham-app
cd ~/graham-app
# Copy all Python files here: app.py, graham.py, quality.py, momentum.py, 
# scorer.py, screener.py, universe.py, sec_data.py, cache.py, 
# api_fetcher.py, requirements.txt
# Copy assets/style.css and assets/style.scss into assets/ folder
```

### 2. Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate   # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Should see (venv) in your prompt
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

Takes ~2 minutes. Installs dash, plotly, pandas, numpy, requests, alpha_vantage.

### 4. (Optional) Alpha Vantage API Key
Get a **free** key at https://www.alphavantage.co/support/#api-key

Create `.env` file in project root:
```
AV_API_KEY=your_key_here
```

Without a key, the app uses `demo` which has rate limits but still works.

### 5. Run
```bash
python app.py
```
### 6. landing pages
http://127.0.0.1:8050/landing/pre-a
See:
```
🚀 Graham Score — Quant Edition
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEC EDGAR (free) + Alpha Vantage (free)

Dash is running on http://127.0.0.1:8050/
```

Open http://localhost:8050 in your browser.

---

## How to Use

### Tab 1: Screener

1. Click **"Load Universe (S&P 500 + 400)"** button
   - Fetches SEC data for ~900 stocks
   - ~15-20 minutes first time (cached 6 months after)
   - Shows progress bar with current stock

2. Results display in ranked table:
   - **#** — Rank by composite score
   - **Graham** — Value score (0-100)
   - **Quality** — Business quality (0-100)
   - **Momentum** — Price momentum (0-100)
   - **Composite** — Weighted score (final rank)
   - **Verdict** — STRONG BUY / BUY / WATCH / HOLD / AVOID

3. Click any row to drill into full analysis

### Tab 2: Analyze

1. Type a ticker: **KO**, **JNJ**, **XOM**, **WMT**, **VZ**
2. Click **Analyze**
3. See full breakdown:
   - **Company header** — Price, P/E, P/B, ROE, Operating Margin
   - **Composite score banner** — Final verdict + pillar breakdown
   - **Graham scorecard** — All 9 Graham criteria with scores
   - **Quality scorecard** — ROE, margins, FCF, revenue growth
   - **Momentum scorecard** — 200-day MA, 12-mo return, relative strength
   - **Charts**:
     - EPS history (10 years)
     - Price vs SPY (normalized to 100)
     - Dividend history
     - Graham Number details

---

## Data Sources (No API Keys!)

| Data | Source | Cost | Refresh |
|------|--------|------|---------|
| Stock prices | Alpha Vantage (free tier) | Free | Daily |
| EPS, Debt, Assets | SEC EDGAR XBRL | Free | Quarterly |
| Operating margins, FCF | SEC EDGAR XBRL | Free | Quarterly |
| Current ratio, Book value | SEC EDGAR XBRL | Free | Quarterly |
| Dividend history | SEC EDGAR XBRL | Free | Quarterly |

**Total cost: $0**

---

## What Each Score Means

### Graham (40%)
Classic Benjamin Graham criteria from "The Intelligent Investor":

| Criterion | Threshold | Points |
|-----------|-----------|--------|
| P/E Ratio | ≤ 15× | 15 |
| P/B Ratio | ≤ 1.5× | 10 |
| P/E × P/B | ≤ 22.5 | 5 |
| Graham Number | Price ≤ 67% | 20 |
| Current Ratio | ≥ 2.0× | 10 |
| Debt/Equity | ≤ 1.0× | 10 |
| EPS Growth | ≥ 33% / no losses | 15 |
| Dividend Track | 20+ years | 10 |
| Net-Net (NNWC) | > Market Cap | 5 |
| **Max** | | **100** |

### Quality (35%)
Modern business quality metrics:

| Criterion | Threshold | Points |
|-----------|-----------|--------|
| Return on Equity | ≥ 15% | 25 |
| EPS Consistency | Up 4 of 5 years | 20 |
| Operating Margin | ≥ 15% | 20 |
| Free Cash Flow | Positive & growing | 20 |
| Revenue Growth | 5-year positive | 15 |
| **Max** | | **100** |

### Momentum (25%)
Technical/market factors:

| Criterion | Threshold | Points |
|-----------|-----------|--------|
| 200-day MA | Price above MA | 30 |
| 12-month Return | > 0% | 30 |
| Relative Strength | vs SPY 12mo | 25 |
| 3-month Drawdown | Not down > 20% | 15 |
| **Max** | | **100** |

---

## Example Stocks to Try

### High Graham (Defensive)
- **KO** (Coca-Cola) — Classic dividend aristocrat, brand moat
- **JNJ** (Johnson & Johnson) — Diversified healthcare
- **XOM** (ExxonMobil) — Energy with high cash returns
- **VZ** (Verizon) — Stable utility-like telecom

### Mixed (Requires Quality Check)
- **MSFT** (Microsoft) — Expensive P/E but high ROE
- **WMT** (Walmart) — Retail with efficiency
- **BAC** (Bank of America) — Cyclical but cheap at times

### Modern Tech (Usually Low Graham, High Quality)
- **AAPL** (Apple) — Brand moat but expensive
- **NVDA** (Nvidia) — Explosive growth but very pricey

---

## Interpreting Results

### STRONG BUY (70+)
✅ Cheap (Graham passes)
✅ High quality business (strong ROE, stable earnings)
✅ Market is confirming (good momentum)

**Action:** Research further, consider position sizing

### BUY (55-70)
✅ Good fundamentals
✅ Mostly positive signals
⚠️ One pillar might be weak

**Action:** Good entry point, watch for momentum

### WATCH (40-55)
⚠️ Mixed signals
✅ Some positives, some concerns

**Action:** Monitor, look for clearer signals

### HOLD/WEAK (25-40)
❌ Multiple concerns
❌ Fails on valuation or quality or momentum

**Action:** Skip, or wait for better entry point

### AVOID (<25)
❌ Fails on multiple pillars
❌ Graham would reject entirely

**Action:** Don't buy

---

## Value Trap Warning

The app shows a **⚠️ Value Trap Risk** banner if:
- Graham score is high (cheap)
- BUT ROE is declining
- AND momentum is weak

This is a "fallen angel" scenario — cheap for a reason. Requires conviction to buy.

---

## Performance Notes

**First load:** ~20 minutes to fetch all 900 stocks from SEC EDGAR
**After that:** Instant (6-month cache)

**Price history:** Fetches as needed, cached 7 days

**Rate limits:** 
- SEC EDGAR: 10 req/sec (we use 3/sec to be polite)
- Alpha Vantage free: 25/day or 5/min (demo key more limited)

If you hit Alpha Vantage limits, the app still works — you just won't see momentum scores until the next day.

---

## Customization

### Modify Weighting
Edit `scorer.py`:
```python
WEIGHTS = {
    "graham":   0.40,   # Change these
    "quality":  0.35,
    "momentum": 0.25,
}
```

### Modify Thresholds
Edit individual `*.py` files:
- `graham.py` — Change P/E, P/B, etc. thresholds
- `quality.py` — Change ROE, margin targets
- `momentum.py` — Change MA period, return targets

### Styling
Edit `assets/style.scss` (source) or `assets/style.css` (compiled).

To recompile SCSS:
```bash
npm install -g sass
sass assets/style.scss assets/style.css
```

---

## Troubleshooting

### "No price history available"
- First time fetching Alpha Vantage data
- Hit rate limit (25/day free tier)
- Solution: Wait 24 hours or get paid API key

### "Ticker not found in SEC database"
- Company doesn't file with SEC (foreign, private, delisted)
- Check: Is it a valid NYSE/NASDAQ ticker?
- Try: SPY, KO, JNJ, WMT, IBM (known good stocks)

### ModuleNotFoundError
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Port 8050 already in use
```bash
python app.py --port 8080
# or kill whatever's using 8050
```

---

## Why This Approach?

Pure Graham was too strict in modern markets (rejected 85% of S&P 500). Adding quality + momentum gives you:

✅ **Graham's downside protection** — Avoid overpaid disaster stocks
✅ **Quality filter** — Avoid value traps (cheap for good reason)
✅ **Momentum confirmation** — Don't fight the market trend

The result: Beating passive S&P 500 returns with less drawdown historically.

---

## References

- Graham, Benjamin. *The Intelligent Investor* (Revised Edition)
- Greenblatt, Joel. *The Little Book That Still Beats the Market*
- SEC EDGAR: https://www.sec.gov/edgar/
- Alpha Vantage: https://www.alphavantage.co/

---

**Questions?** This app is fully transparent — read the Python files to understand every scoring decision.
