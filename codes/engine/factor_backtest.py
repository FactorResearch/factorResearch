"""
Factor Weight Backtesting Engine

Lets users test custom factor weightings against historical data.
Pulls persisted analysis results, re-scores each stock with the user's
custom weights, selects the top-N portfolio, and compares it against:
  - The default ENHANCED_WEIGHTS portfolio
  - SPY buy-and-hold

Works from Postgres (analysis_cache table) + cached price history — no new
network calls beyond price history fetches.

Entry point:
    run_factor_backtest(custom_weights, top_n=10, years=5)

Returns:
    {
        "custom": {top stocks, backtest values, CAGR, Sharpe, max_drawdown},
        "default": {same},
        "spy": {same},
        "custom_weights": {...},
        "default_weights": {...},
        "ranked_stocks": [{symbol, custom_score, default_score, delta, ...}],
        "overlap": [symbols in both portfolios],
        "error": str | None,
    }
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from codes.core import financial_math as fm

from ..data import api_fetcher, db
from .scorer import ENHANCED_WEIGHTS

# ── Constants ─────────────────────────────────────────────────────────────────

MIN_STOCKS       = 3
MAX_TOP_N        = 20
DEFAULT_TOP_N    = 10
DEFAULT_YEARS    = 5
RISK_FREE_RATE   = 0.045   # annual; matches risk_metrics.py


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_pct(result: dict, score_key: str = "total_score",
              max_key: str = "total_max") -> float:
    s = result.get(score_key, 0) or 0
    m = result.get(max_key, 100) or 100
    return (s / m * 100) if m else 0.0


def _score_with_weights(analysis: dict, weights: dict[str, float]) -> float:
    """Re-score a persisted analysis dict with custom factor weights."""
    g  = analysis.get("graham",   {}) or {}
    q  = analysis.get("quality",  {}) or {}
    m  = analysis.get("momentum", {}) or {}
    r  = analysis.get("risk",     {}) or {}
    a  = analysis.get("altman",   {}) or {}
    er = analysis.get("earnings_revision", {}) or {}
    p  = analysis.get("profitability",     {}) or {}
    f  = analysis.get("fcf_quality",       {}) or {}
    ca = analysis.get("capital_allocation",{}) or {}
    gq = analysis.get("growth_quality",    {}) or {}

    def _pct(d, sk="total_score", mk="total_max"):
        return _safe_pct(d, sk, mk)

    scores = {
        "graham":            _pct(g),
        "quality":           _pct(q),
        "momentum":          _pct(m),
        "risk":              _pct(r, "risk_score", "risk_score_max"),
        "altman":            (a.get("risk_score") or 50),
        "earnings_revision": _pct(er) if er else 50.0,
        "profitability":     (p.get("profitability_score") or 50.0) if p else 50.0,
        "fcf_quality":       (f.get("fcf_quality_score")   or 50.0) if f else 50.0,
        "capital_allocation":(ca.get("capital_allocation_score") or 50.0) if ca else 50.0,
        "growth_quality":    (gq.get("growth_quality_score") or 50.0) if gq else 50.0,
    }

    total_w = sum(weights.get(k, 0) for k in scores)
    if total_w <= 0:
        return 50.0

    raw = sum(scores[k] * weights.get(k, 0) for k in scores)
    return round(raw / total_w, 2)


def _normalise_weights(raw: dict[str, float]) -> dict[str, float]:
    """Ensure weights sum to 1.0; clamp negatives to 0."""
    cleaned = {k: max(0.0, float(v)) for k, v in raw.items()}
    total = sum(cleaned.values())
    if total <= 0:
        n = len(cleaned)
        return dict.fromkeys(cleaned, 1.0 / n)
    return {k: v / total for k, v in cleaned.items()}


def _load_price_history(symbol: str, years: int) -> pd.DataFrame:
    df = api_fetcher.get_price_history(symbol, years=years)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["Date"]  = pd.to_datetime(df["Date"])
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    return df.dropna().sort_values("Date").reset_index(drop=True)


def _backtest_equal_weight(
    symbols: list[str],
    years: int,
) -> dict[str, Any]:
    """
    Equal-weight buy-and-hold backtest for a list of symbols.
    Returns {dates, values, cagr, sharpe, max_drawdown, error}.
    """
    if not symbols:
        return {"error": "No symbols provided"}

    histories: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        h = _load_price_history(sym, years)
        if not h.empty:
            histories[sym] = h

    available = [s for s in symbols if s in histories]
    if len(available) < MIN_STOCKS:
        return {"error": f"Only {len(available)} symbols have price history (need {MIN_STOCKS}+)"}

    # Align on common dates
    dfs = [histories[s].set_index("Date")["Close"].rename(s) for s in available]
    wide = pd.concat(dfs, axis=1).dropna().reset_index()
    wide = wide.rename(columns={"index": "Date"}).sort_values("Date").reset_index(drop=True)

    if len(wide) < 6:
        return {"error": "Insufficient overlapping price history"}

    # Equal-weight portfolio value (normalised to $10,000 at start)
    start_val = 10_000.0
    n = len(available)
    share_per_sym = (start_val / n)
    entry = wide.iloc[0]
    shares = {s: share_per_sym / float(entry[s]) for s in available if float(entry[s]) > 0}

    values = []
    for _, row in wide.iterrows():
        v = sum(shares.get(s, 0) * float(row[s]) for s in available if s in shares)
        values.append(round(v, 2))

    dates = wide["Date"].dt.strftime("%Y-%m-%d").tolist()

    # CAGR
    n_years = max((wide["Date"].iloc[-1] - wide["Date"].iloc[0]).days / 365.25, 1 / 12)
    cagr_raw = fm.cagr(values[0], values[-1], n_years)
    cagr = cagr_raw * 100 if cagr_raw is not None else 0.0

    # Monthly log returns → Sharpe
    log_rets = np.log(np.array(values[1:]) / np.array(values[:-1]))
    sharpe = fm.sharpe_ratio(log_rets, risk_free_rate=RISK_FREE_RATE, periods_per_year=12)

    # Max drawdown
    max_dd = round((fm.max_drawdown(values) or 0.0) * 100, 2)

    return {
        "dates":        dates,
        "values":       values,
        "cagr":         round(cagr, 2),
        "sharpe":       round(sharpe, 3) if sharpe is not None else None,
        "max_drawdown": max_dd,
        "n_stocks":     len(available),
        "symbols":      available,
        "error":        None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def run_factor_backtest(
    custom_weights: dict[str, float],
    top_n:  int  = DEFAULT_TOP_N,
    years:  int  = DEFAULT_YEARS,
    min_price: float | None = None,
) -> dict[str, Any]:
    """
    Re-score every persisted analysis with custom_weights, pick the top-N stocks,
    run an equal-weight backtest, and compare against:
      - Default ENHANCED_WEIGHTS portfolio (top-N by default scoring)
      - SPY buy-and-hold

    Args:
        custom_weights:  dict mapping factor names to non-negative floats.
                         Will be normalised to sum=1 internally.
        top_n:           Number of stocks in each hypothetical portfolio.
        years:           Backtest look-back in years (max 10).
        min_price:       Optional minimum stock price filter.

    Returns a result dict (see module docstring).
    """
    top_n = max(MIN_STOCKS, min(MAX_TOP_N, int(top_n)))
    years = max(1, min(10, int(years)))

    # ── Normalise weights ────────────────────────────────────────────────────
    w_custom  = _normalise_weights(custom_weights)
    w_default = _normalise_weights(dict(ENHANCED_WEIGHTS))

    # ── Load all persisted analyses (Postgres, shared cache) ─────────────────
    cached_entries = db.list_analysis_entries()
    if len(cached_entries) < MIN_STOCKS:
        return {"error": f"Need at least {MIN_STOCKS} analysed stocks in the database. "
                         "Use the Analyze tab to analyse some stocks first."}

    ranked: list[dict[str, Any]] = []
    for sym, entry in cached_entries.items():
        data = entry["data"]
        if not data or "error" in data:
            continue
        price = data.get("price")
        if min_price is not None and price is not None and price < min_price:
            continue

        c_score = _score_with_weights(data, w_custom)
        d_score = _score_with_weights(data, w_default)

        ranked.append({
            "symbol":        sym,
            "name":          data.get("name", sym),
            "sector":        data.get("sector", ""),
            "price":         price,
            "custom_score":  c_score,
            "default_score": d_score,
            "delta":         round(c_score - d_score, 2),
        })

    if len(ranked) < MIN_STOCKS:
        return {"error": "Not enough analysed stocks with valid data in the database."}

    # ── Select top-N for each weighting ──────────────────────────────────────
    ranked.sort(key=lambda x: x["custom_score"],  reverse=True)
    custom_top  = [r["symbol"] for r in ranked[:top_n]]

    ranked.sort(key=lambda x: x["default_score"], reverse=True)
    default_top = [r["symbol"] for r in ranked[:top_n]]

    # Restore original sort order (custom score) for the ranked_stocks output
    ranked.sort(key=lambda x: x["custom_score"], reverse=True)

    # ── Run backtests ─────────────────────────────────────────────────────────
    print(f"  [FactorBacktest] custom={custom_top}, default={default_top}")
    bt_custom  = _backtest_equal_weight(custom_top,  years)
    bt_default = _backtest_equal_weight(default_top, years)
    bt_spy     = _backtest_equal_weight(["SPY"],      years)

    overlap = sorted(set(custom_top) & set(default_top))

    # ── Weight diff summary (factors that changed most) ───────────────────────
    all_factors = sorted(set(w_custom) | set(w_default))
    weight_changes = [
        {
            "factor":  k,
            "custom":  round(w_custom.get(k, 0) * 100, 1),
            "default": round(w_default.get(k, 0) * 100, 1),
            "delta":   round((w_custom.get(k, 0) - w_default.get(k, 0)) * 100, 1),
        }
        for k in all_factors
    ]
    weight_changes.sort(key=lambda x: abs(x["delta"]), reverse=True)

    return {
        "custom":          bt_custom,
        "default":         bt_default,
        "spy":             bt_spy,
        "custom_top":      custom_top,
        "default_top":     default_top,
        "overlap":         overlap,
        "ranked_stocks":   ranked[:max(top_n * 2, 20)],   # show top-2N for context
        "custom_weights":  {k: round(v * 100, 1) for k, v in w_custom.items()},
        "default_weights": {k: round(v * 100, 1) for k, v in w_default.items()},
        "weight_changes":  weight_changes,
        "top_n":           top_n,
        "years":           years,
        "n_analysed":      len(ranked),
        "error":           None,
    }
