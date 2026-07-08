"""
Momentum scoring engine — 100 points total.

Criteria:
  200-day Moving Average   price > MA     30 pts
  12-month Return          > 0%           30 pts
  Relative Strength        vs SPY 12mo    25 pts
  3-month Drawdown         not down >20%  15 pts

19.2A — 12-Month Return uses skip-month construction (12-2 momentum):
  excludes the most recent month to remove short-term reversal
  contamination, per standard academic momentum methodology.

19.2B — Volatility-Scaled Momentum (Daniel & Moskowitz 2016,
  "Momentum Crashes"): the skip-month 12M return divided by trailing
  realized volatility, exposed as `vol_scaled_momentum` / `vol_annual`
  in the output dict. Display/diagnostic only — does not change the
  100-point scoring breakdown above.
"""

import pandas as pd
import numpy as np


def score(price_hist: pd.DataFrame, spy_hist: pd.DataFrame, symbol: str,
          sector_avg_return_12m: float | None = None) -> dict:
    """
    score() accepts price history DataFrames (Date, Close columns).
    Returns momentum score dict compatible with scorer.py.

    19.2C — sector_avg_return_12m (optional): the mean skip-month 12M
    return across the stock's sector peers (computed by the caller from
    screener universe results). When provided, `industry_relative_momentum`
    = this stock's return_12m minus the sector average, isolating stock
    alpha from sector-wide tailwinds. Display/diagnostic only — does not
    change the 100-point scoring breakdown.
    """
    criteria = []

    if price_hist is None or price_hist.empty:
        return _empty_score("No price history available")

    # Ensure sorted chronologically
    hist = price_hist.copy()
    hist["Date"] = pd.to_datetime(hist["Date"])
    hist = hist.sort_values("Date").reset_index(drop=True)

    if len(hist) < 6:
        return _empty_score("Insufficient price history (need 6+ months)")

    current_price = hist["Close"].iloc[-1]

    # ── 200-day Moving Average (use monthly data: ~10 months ≈ 200 days) ─────
    ma_periods = min(10, len(hist))
    ma200 = hist["Close"].tail(ma_periods).mean()
    above_ma = current_price > ma200

    if above_ma:
        pct_above = (current_price - ma200) / ma200 * 100
        ma_score, ma_note = 30, f"Price ${current_price:.2f} is {pct_above:.1f}% above 200-day MA ${ma200:.2f}"
    else:
        pct_below = (ma200 - current_price) / ma200 * 100
        ma_score, ma_note = 0, f"Price ${current_price:.2f} is {pct_below:.1f}% below 200-day MA ${ma200:.2f}"

    criteria.append({
        "label":       "200-Day Moving Average",
        "requirement": "Price above MA",
        "actual":      f"MA ${ma200:.2f}",
        "score":       ma_score,
        "max":         30,
        "note":        ma_note,
    })

    # ── 12-Month Return (skip-month: 12-2 momentum, excludes most recent month
    #    to remove short-term reversal contamination — standard academic
    #    momentum construction) ────────────────────────────────────────────────
    return_12m = None
    if len(hist) >= 13:
        price_1m_ago  = hist["Close"].iloc[-2]
        price_13m_ago = hist["Close"].iloc[-13]
        if price_13m_ago > 0:
            return_12m = (price_1m_ago - price_13m_ago) / price_13m_ago * 100

    # ── Volatility-Scaled Momentum (Daniel & Moskowitz 2016) ──────────────────
    # Divides the skip-month 12M return by trailing realized volatility so
    # stocks with the same return but lower vol rank higher.
    vol_annual = None
    vol_scaled_momentum = None
    if len(hist) >= 13:
        monthly_rets = hist["Close"].tail(13).pct_change().dropna()
        if len(monthly_rets) >= 2:
            vol_monthly = monthly_rets.std()
            if vol_monthly and vol_monthly > 0:
                vol_annual = float(vol_monthly * (12 ** 0.5) * 100)
                if return_12m is not None and vol_annual > 0:
                    vol_scaled_momentum = round(return_12m / vol_annual, 4)

    if return_12m is None:
        r12_score, r12_note = 0, "Insufficient history for 12-month return"
    elif return_12m >= 20:
        r12_score, r12_note = 30, f"12-month return +{return_12m:.1f}% — strong momentum"
    elif return_12m >= 10:
        r12_score, r12_note = 20, f"12-month return +{return_12m:.1f}% — positive momentum"
    elif return_12m >= 0:
        r12_score, r12_note = 10, f"12-month return +{return_12m:.1f}% — flat"
    else:
        r12_score, r12_note = 0,  f"12-month return {return_12m:.1f}% — negative momentum"

    criteria.append({
        "label":       "12-Month Return",
        "requirement": "> 0% (12-2 skip-month)",
        "actual":      f"{return_12m:+.1f}%" if return_12m is not None else "N/A",
        "score":       r12_score,
        "max":         30,
        "note":        r12_note,
    })

    # ── Relative Strength vs SPY ──────────────────────────────────────────────
    rs_score, rs_note = 0, "SPY history not available for comparison"

    if spy_hist is not None and not spy_hist.empty:
        spy = spy_hist.copy()
        spy["Date"] = pd.to_datetime(spy["Date"])
        spy = spy.sort_values("Date").reset_index(drop=True)

        spy_return_12m = None
        if len(spy) >= 13:
            spy_1m_ago  = spy["Close"].iloc[-2]
            spy_13m_ago = spy["Close"].iloc[-13]
            if spy_13m_ago > 0:
                spy_return_12m = (spy_1m_ago - spy_13m_ago) / spy_13m_ago * 100

        if return_12m is not None and spy_return_12m is not None:
            alpha = return_12m - spy_return_12m
            if alpha >= 10:
                rs_score, rs_note = 25, f"Outperforming SPY by {alpha:.1f}% — strong relative strength"
            elif alpha >= 0:
                rs_score, rs_note = 15, f"Outperforming SPY by {alpha:.1f}% — in line or slightly ahead"
            elif alpha >= -10:
                rs_score, rs_note = 5,  f"Underperforming SPY by {abs(alpha):.1f}% — slight lag"
            else:
                rs_score, rs_note = 0,  f"Underperforming SPY by {abs(alpha):.1f}% — weak relative strength"

    criteria.append({
        "label":       "Relative Strength vs SPY",
        "requirement": "Outperforming SPY",
        "actual":      "See note",
        "score":       rs_score,
        "max":         25,
        "note":        rs_note,
    })

    # ── 3-Month Drawdown ─────────────────────────────────────────────────────
    return_3m = None
    if len(hist) >= 3:
        price_3m_ago = hist["Close"].iloc[-3]
        if price_3m_ago > 0:
            return_3m = (current_price - price_3m_ago) / price_3m_ago * 100

    if return_3m is None:
        dd_score, dd_note = 0, "Insufficient history for 3-month check"
    elif return_3m >= 0:
        dd_score, dd_note = 15, f"3-month return +{return_3m:.1f}% — no drawdown concern"
    elif return_3m >= -10:
        dd_score, dd_note = 8,  f"3-month return {return_3m:.1f}% — minor pullback"
    elif return_3m >= -20:
        dd_score, dd_note = 3,  f"3-month return {return_3m:.1f}% — significant drawdown"
    else:
        dd_score, dd_note = 0,  f"3-month return {return_3m:.1f}% — severe drawdown — avoid catching falling knife"

    criteria.append({
        "label":       "3-Month Drawdown Check",
        "requirement": "Not down > 20%",
        "actual":      f"{return_3m:+.1f}%" if return_3m is not None else "N/A",
        "score":       dd_score,
        "max":         15,
        "note":        dd_note,
    })

    # ── Industry-Relative Momentum (19.2C) ────────────────────────────────────
    industry_relative_momentum = None
    if return_12m is not None and sector_avg_return_12m is not None:
        industry_relative_momentum = round(return_12m - sector_avg_return_12m, 4)

    total_score = sum(c["score"] for c in criteria)
    total_max   = sum(c["max"]   for c in criteria)

    return {
        "price":                current_price,
        "ma200":                ma200,
        "above_ma":             above_ma,
        "return_12m":           return_12m,
        "return_3m":            return_3m,
        "vol_annual":           round(vol_annual, 2) if vol_annual is not None else None,
        "vol_scaled_momentum":  vol_scaled_momentum,
        "sector_avg_return_12m": sector_avg_return_12m,
        "industry_relative_momentum": industry_relative_momentum,
        "total_score":          total_score,
        "total_max":            total_max,
        "criteria":             criteria,
    }


def _empty_score(reason: str) -> dict:
    criteria = [
        {"label": c, "requirement": "", "actual": "N/A",
         "score": 0, "max": m, "note": reason}
        for c, m in [
            ("200-Day Moving Average", 30),
            ("12-Month Return", 30),
            ("Relative Strength vs SPY", 25),
            ("3-Month Drawdown Check", 15),
        ]
    ]
    return {
        "price":               None,
        "ma200":               None,
        "above_ma":            None,
        "return_12m":          None,
        "return_3m":           None,
        "vol_annual":          None,
        "vol_scaled_momentum": None,
        "sector_avg_return_12m":       None,
        "industry_relative_momentum": None,
        "total_score":         0,
        "total_max":           100,
        "criteria":            criteria,
        "error":               reason,
    }