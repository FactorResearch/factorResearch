"""
Co-Momentum Model — Lou & Polk (2012) crowding signal.

When top-momentum stocks become highly correlated with each other, the
momentum trade is "crowded": average forward returns fall and crash risk
rises. This measures average pairwise return correlation among a given
top-momentum basket and expresses it as a percentile against its own
rolling history — "high" is relative to the recent past, not an
arbitrary absolute threshold.

Reference:
  Lou & Polk (2012) "Comomentum: Inferring Arbitrage Activity from
  Return Correlations"
"""

import numpy as np
import pandas as pd

HISTORY_MONTHS = 36  # rolling window for percentile ranking


def _build_returns_matrix(symbols: list[str], price_histories: dict) -> pd.DataFrame:
    """Wide DataFrame of monthly pct-change returns, outer-joined on Date."""
    cols = {}
    for sym in symbols:
        hist = price_histories.get(sym)
        if hist is None or hist.empty:
            continue
        h = hist.copy()
        h["Date"] = pd.to_datetime(h["Date"])
        h = h.sort_values("Date").set_index("Date")["Close"]
        h = pd.to_numeric(h, errors="coerce")
        rets = h.pct_change().dropna()
        if not rets.empty:
            cols[sym] = rets
    if len(cols) < 2:
        return pd.DataFrame()
    return pd.concat(cols, axis=1).dropna(how="all")


def _avg_pairwise_corr(window: pd.DataFrame) -> float | None:
    """Average off-diagonal correlation across all symbol pairs in `window`."""
    window = window.dropna(axis=1, how="any")
    if window.shape[1] < 2 or window.shape[0] < 2:
        return None
    corr = window.corr().values
    n = corr.shape[0]
    off_diag = corr[~np.eye(n, dtype=bool)]
    off_diag = off_diag[np.isfinite(off_diag)]
    if off_diag.size == 0:
        return None
    return float(np.mean(off_diag))


def calc_comomentum(
    top_momentum_symbols: list[str],
    price_histories: dict,
    lookback_months: int = 6,
) -> dict:
    """
    Current co-momentum (crowding) score for a top-momentum basket, and its
    percentile rank against its own rolling history.

    Returns:
      {
        "raw_score":  float | None,   # avg pairwise correlation, current window
        "percentile": float,          # 0-100, current vs rolling history
        "signal":     "HIGH" | "NORMAL" | "LOW",
        "n_symbols":  int,             # symbols actually usable
        "n_history":  int,             # historical windows used for percentile
        "error":      str | None,
      }
    """
    def _neutral(reason: str) -> dict:
        return {
            "raw_score": None, "percentile": 50.0, "signal": "NORMAL",
            "n_symbols": 0, "n_history": 0, "error": reason,
        }

    if not top_momentum_symbols or not price_histories:
        return _neutral("No symbols or price history provided")

    returns = _build_returns_matrix(top_momentum_symbols, price_histories)
    if returns.empty or len(returns) < lookback_months:
        return _neutral("Insufficient overlapping return history")

    n = len(returns)
    start_idx = max(lookback_months - 1, n - HISTORY_MONTHS)
    history_scores = []
    for i in range(start_idx, n):
        window = returns.iloc[max(0, i - lookback_months + 1): i + 1]
        score = _avg_pairwise_corr(window)
        if score is not None:
            history_scores.append(score)

    if not history_scores:
        return _neutral("Could not compute pairwise correlations")

    current = history_scores[-1]
    percentile = round(
        float(np.sum(np.array(history_scores) <= current) / len(history_scores) * 100), 2
    )

    if percentile >= 75:
        signal = "HIGH"
    elif percentile <= 25:
        signal = "LOW"
    else:
        signal = "NORMAL"

    return {
        "raw_score":  round(current, 4),
        "percentile": percentile,
        "signal":     signal,
        "n_symbols":  returns.shape[1],
        "n_history":  len(history_scores),
        "error":      None,
    }