"""
Full Backtest Engine — strategies beyond the equal-weight buy-and-hold
backtest already implemented in codes/engine/factor_backtest.py.

Strategies:
  1. momentum_rotation   — monthly rebalance, top-decile by trailing 12mo price momentum
  2. score_filtered      — hold composite_score >= threshold, rebalance quarterly
  3. factor_combo        — Graham pass + Piotroski F >= 7 + positive FCF screen
  4. walk_forward         — re-run any of the above over rolling 3Y/5Y/10Y windows

[BACKTEST BIAS WARNING] — READ BEFORE USING RESULTS
────────────────────────────────────────────────────────────────────────────
codes/data/db.py stores exactly ONE `analysis_cache` row per ticker — the
most recent full analysis, shared across all users so we don't re-run SEC
fetches and scoring for a stock that's already been analysed. There is no
dated history of past scores.

Consequences for this module:
  - score_filtered() and factor_combo() screen the universe using TODAY's
    persisted composite_score / Piotroski F-Score / FCF sign. That same
    (current) score is then applied across the ENTIRE historical backtest
    window — i.e. a stock is treated as if it always had its current score,
    which it did not. This is unavoidable look-ahead bias with the current
    shared-cache architecture (fixing it would require snapshotting scores
    by date, which is out of scope here).
  - momentum_rotation() is NOT affected: it is computed purely from monthly
    price history, which is genuinely point-in-time (a stock's June 2019
    price is what it was in June 2019, regardless of when we look it up).
  - walk_forward() inherits the bias of whichever strategy function it wraps.

Every result dict from a biased strategy sets `"look_ahead_bias": True`.
UI callers MUST surface this as a "[BACKTEST BIAS WARNING]" badge whenever
the flag is true, and must not present these as historically realistic
walk-forward returns.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from codes.core import financial_math as fm

from ..data import api_fetcher, db
from . import factor_snapshot

MIN_STOCKS     = 3
MAX_TOP_N      = 30
RISK_FREE_RATE = 0.045   # annual; matches risk_metrics.py / factor_backtest.py
MONTHS_PER_YEAR = 12


# ── Shared helpers ────────────────────────────────────────────────────────────

def _load_price_history(symbol: str, years: int) -> pd.DataFrame:
    df = api_fetcher.get_price_history(symbol, years=years)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["Date"]  = pd.to_datetime(df["Date"])
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    return df.dropna().sort_values("Date").reset_index(drop=True)


def _build_price_matrix(symbols: list[str], years: int) -> pd.DataFrame:
    """Wide Date-indexed DataFrame of monthly closes, one column per symbol."""
    cols = {}
    for sym in symbols:
        h = _load_price_history(sym, years)
        if not h.empty:
            cols[sym] = h.set_index("Date")["Close"]
    if not cols:
        return pd.DataFrame()
    wide = pd.concat(cols, axis=1).sort_index()
    wide = wide.ffill(limit=2)   # tolerate 1-2 missing months (holidays/gaps)
    return wide


def _load_cached_universe() -> dict[str, dict]:
    """All symbols with a persisted full `analysis` result (Postgres, shared cache)."""
    out = {}
    for sym, entry in db.list_analysis_entries().items():
        data = entry["data"]
        if data and "error" not in data:
            out[sym] = data
    return out


def _compute_risk_metrics(values: list[float], spy_values: list[float] | None = None) -> dict[str, Any]:
    """Sharpe, Sortino, Calmar, Beta, Alpha, Win Rate, CAGR, Max Drawdown from a monthly value series."""
    empty = {
        "cagr": None, "sharpe": None, "sortino": None, "calmar": None,
        "max_drawdown": None, "win_rate": None, "beta": None, "alpha": None,
    }
    arr = np.array(values, dtype=float)
    if len(arr) < 3 or arr[0] <= 0:
        return empty

    rets = np.diff(arr) / arr[:-1]
    n_months = len(rets)
    n_years = n_months / MONTHS_PER_YEAR
    total_return = arr[-1] / arr[0] - 1
    cagr = fm.cagr(1.0, 1.0 + total_return, n_years) or 0.0

    sharpe = fm.sharpe_ratio(
        rets,
        risk_free_rate=RISK_FREE_RATE,
        periods_per_year=MONTHS_PER_YEAR,
    )

    sortino = fm.sortino_ratio(
        rets,
        annual_return=cagr,
        risk_free_rate=RISK_FREE_RATE,
        periods_per_year=MONTHS_PER_YEAR,
    )

    max_dd = fm.max_drawdown(arr) or 0.0
    calmar = fm.calmar_ratio(cagr, max_dd)

    win_rate = float(np.mean(rets > 0)) if n_months > 0 else None

    beta = alpha = None
    if spy_values is not None and len(spy_values) == len(values):
        spy_arr = np.array(spy_values, dtype=float)
        if spy_arr[0] > 0:
            spy_rets = np.diff(spy_arr) / spy_arr[:-1]
            if len(spy_rets) == n_months and n_months > 1:
                beta = fm.beta(rets, spy_rets)
                if beta is not None:
                    spy_total = spy_arr[-1] / spy_arr[0] - 1
                    spy_cagr = fm.cagr(1.0, 1.0 + spy_total, n_years) or 0.0
                    alpha = fm.alpha(cagr, spy_cagr, beta, risk_free_rate=RISK_FREE_RATE)

    return {
        "cagr":         round(cagr * 100, 2),
        "sharpe":       round(sharpe, 3) if sharpe is not None else None,
        "sortino":      round(sortino, 3) if sortino is not None else None,
        "calmar":       round(calmar, 3) if calmar is not None else None,
        "max_drawdown": round(max_dd * 100, 2),
        "win_rate":     round(win_rate * 100, 1) if win_rate is not None else None,
        "beta":         round(beta, 3) if beta is not None else None,
        "alpha":        round(alpha * 100, 2) if alpha is not None else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Strategy 1 — Momentum Rotation (point-in-time correct; price data only)
# ══════════════════════════════════════════════════════════════════════════════

def momentum_rotation(top_n: int = 10, years: int = 5, rebalance_months: int = 1) -> dict[str, Any]:
    """
    Monthly (or `rebalance_months`-interval) rebalance into the top-decile
    (or top_n) stocks by trailing 12-month price return. Equal-weighted.

    Uses only monthly price history — genuinely point-in-time correct,
    no look-ahead bias.
    """
    top_n = max(MIN_STOCKS, min(MAX_TOP_N, int(top_n)))
    universe = _load_cached_universe()
    symbols = list(universe.keys())
    if len(symbols) < MIN_STOCKS:
        return {"error": f"Need at least {MIN_STOCKS} analysed stocks in the database.", "look_ahead_bias": False}

    wide = _build_price_matrix(symbols + ["SPY"], years)
    if wide.empty or "SPY" not in wide.columns or len(wide) < 14:
        return {"error": "Insufficient price history for momentum rotation.", "look_ahead_bias": False}

    lookback = 12  # months, for trailing momentum
    if len(wide) <= lookback:
        return {"error": "Insufficient history for a 12-month momentum lookback.", "look_ahead_bias": False}

    rebalance_idx = list(range(lookback, len(wide), rebalance_months))
    if not rebalance_idx or rebalance_idx[-1] != len(wide) - 1:
        rebalance_idx.append(len(wide) - 1)

    dates = wide.index.tolist()
    port_values = [10_000.0]
    spy_values  = [10_000.0]
    port_dates  = [dates[lookback]]

    current_symbols: list[str] = []
    current_shares: dict[str, float] = {}
    spy_shares = spy_values[0] / float(wide["SPY"].iloc[lookback])

    for i in range(1, len(rebalance_idx)):
        prev_i, this_i = rebalance_idx[i - 1], rebalance_idx[i]

        # Score momentum as of prev_i using trailing `lookback` months
        scores = {}
        for sym in symbols:
            series = wide[sym]
            past, now = series.iloc[prev_i - lookback], series.iloc[prev_i]
            if pd.notna(past) and pd.notna(now) and past > 0:
                scores[sym] = now / past - 1

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        current_symbols = [s for s, _ in ranked]
        if not current_symbols:
            continue

        # Re-equal-weight into the selected symbols at prev_i's price
        segment_value = port_values[-1]
        alloc = segment_value / len(current_symbols)
        current_shares = {
            s: alloc / float(wide[s].iloc[prev_i])
            for s in current_symbols
            if pd.notna(wide[s].iloc[prev_i]) and wide[s].iloc[prev_i] > 0
        }

        # Walk value forward to this_i
        pv = sum(sh * float(wide[s].iloc[this_i]) for s, sh in current_shares.items()
                 if pd.notna(wide[s].iloc[this_i]))
        port_values.append(pv if pv > 0 else port_values[-1])
        spy_values.append(spy_shares * float(wide["SPY"].iloc[this_i]))
        port_dates.append(dates[this_i])

    metrics = _compute_risk_metrics(port_values, spy_values)

    return {
        "strategy":       "momentum_rotation",
        "dates":          [d.strftime("%Y-%m-%d") for d in port_dates],
        "values":         [round(v, 2) for v in port_values],
        "spy_values":     [round(v, 2) for v in spy_values],
        "final_symbols":  current_symbols,
        "top_n":          top_n,
        "rebalance_months": rebalance_months,
        **metrics,
        "look_ahead_bias": False,
        "error":          None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Strategy 2 — Score-Filtered (uses current persisted composite_score — BIASED)
# ══════════════════════════════════════════════════════════════════════════════

def score_filtered(min_score: float = 65.0, top_n: int = 20, years: int = 5,
                    rebalance_months: int = 3) -> dict[str, Any]:
    """
    Hold stocks whose composite score >= min_score at each rebalance date.
    Uses factor_snapshot.get_factor_scores_asof() (Layer 5) for symbols with
    sufficient dated history; falls back to today's persisted composite_score
    for symbols without it. look_ahead_bias reflects whether ANY fallback
    was used across the whole run.
    """
    from .scorer import ENHANCED_WEIGHTS

    universe = _load_cached_universe()
    candidates = list(universe.keys())
    if len(candidates) < MIN_STOCKS:
        return {"error": f"Need at least {MIN_STOCKS} analysed stocks in the database.",
                "look_ahead_bias": True}

    fallback_used = {"flag": False}
    snapshot_history = factor_snapshot.load_history(candidates)
    top_n = max(MIN_STOCKS, min(MAX_TOP_N, int(top_n)))

    def _today_composite(sym: str) -> float | None:
        data = universe[sym]
        enhanced = data.get("enhanced") or {}
        comp = data.get("composite") or {}
        return enhanced.get("composite_score") or comp.get("composite_score")

    def qualify(sym: str, as_of: str) -> float | None:
        if factor_snapshot.history_has_sufficient_dates(snapshot_history, sym):
            scores = factor_snapshot.history_scores_asof(snapshot_history, sym, as_of)
            usable = {k: v for k, v in scores.items() if v.get("max_score")}
            if usable:
                total_w = sum(ENHANCED_WEIGHTS.get(k, 0) for k in usable)
                if total_w > 0:
                    raw = sum(
                        (v["score"] / v["max_score"] * 100) * ENHANCED_WEIGHTS.get(k, 0)
                        for k, v in usable.items()
                    )
                    score = raw / total_w
                    return score if score >= min_score else None
        # Fallback: today's score, applied retroactively (biased)
        fallback_used["flag"] = True
        today_score = _today_composite(sym)
        return today_score if today_score is not None and today_score >= min_score else None

    result = _rebalanced_dynamic_qualify_backtest(
        candidates, years, rebalance_months, qualify, max_holdings=top_n
    )
    result.update({
        "strategy":         "score_filtered",
        "min_score":        min_score,
        "top_n":            top_n,
        "look_ahead_bias":  fallback_used["flag"],
    })
    return result
# ══════════════════════════════════════════════════════════════════════════════
# Strategy 3 — Factor Combo (Graham pass + Piotroski F>=7 + positive FCF)
# ══════════════════════════════════════════════════════════════════════════════

def factor_combo(min_piotroski: int = 7, min_graham_pct: float = 50.0,
                  years: int = 5, rebalance_months: int = 3) -> dict[str, Any]:
    """
    Screen: Graham pct >= min_graham_pct AND Piotroski F-Score >= min_piotroski
    AND positive FCF. Graham/Piotroski use factor_snapshot as-of data when a
    symbol has sufficient history (Layer 5); FCF sign still uses today's
    value (raw dollar FCF isn't captured in factor_score snapshots, only the
    0-100 fcf_quality score) — this one check remains retroactively applied
    and is the reason look_ahead_bias may still be True even when
    Graham/Piotroski are point-in-time correct.
    """
    universe = _load_cached_universe()
    candidates = list(universe.keys())
    if len(candidates) < MIN_STOCKS:
        return {"error": f"Need at least {MIN_STOCKS} analysed stocks in the database.",
                "look_ahead_bias": True}

    fallback_used = {"flag": False}
    snapshot_history = factor_snapshot.load_history(candidates)

    def _today_fcf_positive(sym: str) -> bool:
        fcf = universe[sym].get("fcf_quality") or {}
        val = fcf.get("fcf")
        return val is not None and val > 0

    def qualify(sym: str, as_of: str) -> bool | None:
        graham_ok = piotroski_ok = None
        if factor_snapshot.history_has_sufficient_dates(snapshot_history, sym):
            scores = factor_snapshot.history_scores_asof(snapshot_history, sym, as_of)
            g = scores.get("graham")
            p = scores.get("piotroski")
            if g and g.get("max_score"):
                graham_ok = (g["score"] / g["max_score"] * 100) >= min_graham_pct
            if p and p.get("max_score"):
                piotroski_ok = p["score"] >= min_piotroski

        if graham_ok is None or piotroski_ok is None:
            fallback_used["flag"] = True
            data = universe[sym]
            g_data = data.get("graham") or {}
            p_data = data.get("piotroski") or {}
            g_max = g_data.get("total_max") or 100
            graham_ok = (g_data.get("total_score", 0) / g_max * 100) >= min_graham_pct if g_max else False
            piotroski_ok = (p_data.get("f_score", 0) or 0) >= min_piotroski

        # FCF sign always retroactive today's-value (documented above)
        fallback_used["flag"] = True
        fcf_ok = _today_fcf_positive(sym)

        return bool(graham_ok and piotroski_ok and fcf_ok)

    result = _rebalanced_dynamic_qualify_backtest(candidates, years, rebalance_months, qualify)
    result.update({
        "strategy":         "factor_combo",
        "min_piotroski":    min_piotroski,
        "min_graham_pct":   min_graham_pct,
        "look_ahead_bias":  fallback_used["flag"],
    })
    return result
def _rebalanced_dynamic_qualify_backtest(
    candidate_symbols: list[str],
    years: int,
    rebalance_months: int,
    qualify_fn,
    max_holdings: int | None = None,
) -> dict[str, Any]:
    """
    Like _rebalanced_equal_weight_backtest, but re-evaluates which symbols
    qualify AT EACH REBALANCE DATE via qualify_fn, instead of using a
    single fixed symbol list for the whole window (ISSUE_012 Layer 5).

    qualify_fn returns a truthy rank or None. Numeric ranks are sorted before
    max_holdings is applied; boolean screens preserve candidate order.
    """
    wide = _build_price_matrix(candidate_symbols + ["SPY"], years)
    if wide.empty or "SPY" not in wide.columns or len(wide) < 6:
        return {"error": "Insufficient overlapping price history.", "values": [], "dates": []}

    available = [s for s in candidate_symbols if s in wide.columns]
    if len(available) < MIN_STOCKS:
        return {"error": f"Only {len(available)} symbols have price history.", "values": [], "dates": []}

    dates = wide.index.tolist()
    rebalance_idx = list(range(0, len(wide), rebalance_months))
    if rebalance_idx[-1] != len(wide) - 1:
        rebalance_idx.append(len(wide) - 1)

    port_values = [10_000.0]
    spy_values  = [10_000.0]
    port_dates  = [dates[0]]
    spy_shares  = spy_values[0] / float(wide["SPY"].iloc[0])
    last_qualifying: list[str] = []

    for i in range(1, len(rebalance_idx)):
        prev_i, this_i = rebalance_idx[i - 1], rebalance_idx[i]
        as_of = dates[prev_i].strftime("%Y-%m-%d")

        ranked = []
        for s in available:
            if pd.isna(wide[s].iloc[prev_i]) or wide[s].iloc[prev_i] <= 0:
                continue
            result = qualify_fn(s, as_of)
            if result is None:
                continue  # no data at all — exclude rather than guess
            if result:
                ranked.append((s, float(result)))

        if max_holdings is not None:
            ranked.sort(key=lambda item: item[1], reverse=True)
        qualifying = [symbol for symbol, _rank in ranked[:max_holdings]]

        if not qualifying:
            qualifying = last_qualifying  # hold previous allocation if nothing qualifies this period
        else:
            last_qualifying = qualifying

        if not qualifying:
            continue

        alloc = port_values[-1] / len(qualifying)
        shares = {s: alloc / float(wide[s].iloc[prev_i]) for s in qualifying}
        pv = sum(sh * float(wide[s].iloc[this_i]) for s, sh in shares.items()
                 if pd.notna(wide[s].iloc[this_i]))
        port_values.append(pv if pv > 0 else port_values[-1])
        spy_values.append(spy_shares * float(wide["SPY"].iloc[this_i]))
        port_dates.append(dates[this_i])

    metrics = _compute_risk_metrics(port_values, spy_values)
    return {
        "dates":            [d.strftime("%Y-%m-%d") for d in port_dates],
        "values":           [round(v, 2) for v in port_values],
        "spy_values":       [round(v, 2) for v in spy_values],
        "symbols":          available,
        "final_symbols":    last_qualifying,
        "n_stocks":         len(available),
        "rebalance_months": rebalance_months,
        **metrics,
        "error": None,
    }

# ══════════════════════════════════════════════════════════════════════════════
# Strategy 4 — Walk-Forward Rolling Windows
# ══════════════════════════════════════════════════════════════════════════════

def walk_forward(strategy_fn: Callable[..., dict], windows: tuple[int, ...] = (3, 5, 10),
                  **strategy_kwargs) -> dict[str, Any]:
    """
    Re-run `strategy_fn` (one of momentum_rotation / score_filtered /
    factor_combo) over each rolling window length in `windows` (years).

    Inherits look_ahead_bias from the wrapped strategy — see module docstring.
    """
    results = {}
    bias = None
    for yrs in windows:
        kwargs = dict(strategy_kwargs)
        kwargs["years"] = yrs
        r = strategy_fn(**kwargs)
        bias = r.get("look_ahead_bias", bias)
        results[f"{yrs}y"] = r

    return {
        "strategy":        f"walk_forward[{strategy_fn.__name__}]",
        "windows":         windows,
        "results":         results,
        "look_ahead_bias": bias,
        "error":           None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Strategy comparison
# ══════════════════════════════════════════════════════════════════════════════

def compare_strategies(strategies: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    Build a side-by-side comparison table from a dict of already-computed
    strategy result dicts (e.g. {"Momentum Rotation": momentum_rotation(...),
    "Score Filtered": score_filtered(...), ...}).

    Returns a table plus a `has_bias` flag so the UI can render a single
    [BACKTEST BIAS WARNING] banner if any included strategy is biased.
    """
    rows = []
    has_bias = False
    for name, r in strategies.items():
        if r.get("error"):
            rows.append({"strategy": name, "error": r["error"]})
            continue
        if r.get("look_ahead_bias"):
            has_bias = True
        rows.append({
            "strategy":      name,
            "cagr":          r.get("cagr"),
            "sharpe":        r.get("sharpe"),
            "sortino":       r.get("sortino"),
            "calmar":        r.get("calmar"),
            "max_drawdown":  r.get("max_drawdown"),
            "win_rate":      r.get("win_rate"),
            "beta":          r.get("beta"),
            "alpha":         r.get("alpha"),
            "look_ahead_bias": r.get("look_ahead_bias", False),
        })

    return {
        "rows":     rows,
        "has_bias": has_bias,
        "error":    None,
    }
