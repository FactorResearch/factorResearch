"""
SPY Benchmark Model — pure math layer.

Python port of SPYBenchmarkModel.swift (see BiasEngine_Python_Rewrite.md).

Given price history for SPY and a target (stock or portfolio aggregate),
compute comparison stats. No UI, no opinions, no bias labels — numbers only.
This module must never contain verdict strings ("Buy"/"Outperform Bias"/etc).

Inputs: monthly price history DataFrames with 'Date' and 'Close' columns,
same convention used across codes/models (momentum.py, risk_metrics.py).

probability_outperform is derived by bootstrap-resampling the historical
monthly log-return distributions of target and SPY (not from beta alone),
mirroring the Monte Carlo approach already used in codes/portfolio.py.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from codes.core import financial_math as fm

MONTHS_PER_YEAR = 12


# ── Helpers ───────────────────────────────────────────────────────────────────

def _prep(hist: pd.DataFrame) -> pd.DataFrame:
    df = hist.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"])
    df = df[df["Close"] > 0].sort_values("Date").reset_index(drop=True)
    return df


def _align(target: pd.DataFrame, spy: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Inner-join on Date so both series share the same length/date range."""
    merged = target[["Date", "Close"]].merge(
        spy[["Date", "Close"]], on="Date", how="inner", suffixes=("_t", "_s")
    )
    t = merged[["Date", "Close_t"]].rename(columns={"Close_t": "Close"})
    s = merged[["Date", "Close_s"]].rename(columns={"Close_s": "Close"})
    return t.reset_index(drop=True), s.reset_index(drop=True)


def _normalise(prices: np.ndarray) -> list[float]:
    """Rebase a price series to 100 at the start date."""
    if len(prices) == 0 or prices[0] <= 0:
        return []
    return [round(float(p / prices[0] * 100), 4) for p in prices]


def _cagr(prices: np.ndarray, n_years: float) -> float | None:
    if len(prices) < 2 or prices[0] <= 0 or n_years <= 0:
        return None
    result = fm.cagr(prices[0], prices[-1], n_years)
    return result * 100 if result is not None else None


def _beta_alpha(target_rets: np.ndarray, spy_rets: np.ndarray,
                 cagr_target: float | None, cagr_spy: float | None,
                 risk_free_rate: float = 0.045) -> tuple[float | None, float | None]:
    """Beta via covariance/variance; annualised Jensen's alpha vs CAPM."""
    if len(target_rets) < 2 or len(spy_rets) < 2:
        return None, None
    beta = fm.beta(target_rets, spy_rets)
    if beta is None:
        return None, None
    if cagr_target is None or cagr_spy is None:
        return beta, None
    alpha = fm.alpha(
        cagr_target / 100,
        cagr_spy / 100,
        beta,
        risk_free_rate=risk_free_rate,
    )
    return beta, alpha * 100 if alpha is not None else None  # alpha as annualised %


def _bootstrap_probability_outperform(
    target_rets: np.ndarray,
    spy_rets: np.ndarray,
    horizon_months: int = 12,
    n_sims: int = 2000,
    seed: int = 42,
) -> float | None:
    """
    Bootstrap resample historical monthly log-returns (paired by month, so
    correlation is preserved) to build forward return distributions for the
    target and for SPY, then estimate P(target cumulative return > SPY
    cumulative return) over `horizon_months`.
    """
    n = min(len(target_rets), len(spy_rets))
    if n < 2:
        return None

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_sims, horizon_months))

    target_paths = target_rets[idx].sum(axis=1)
    spy_paths = spy_rets[idx].sum(axis=1)

    wins = float(np.sum(target_paths > spy_paths))
    return round(wins / n_sims, 4)


# ── Main ──────────────────────────────────────────────────────────────────────

def compute_benchmark(
    target_hist: pd.DataFrame,
    spy_hist: pd.DataFrame,
    horizon_months: int = 12,
    n_sims: int = 2000,
    seed: int = 42,
) -> dict[str, Any]:
    """
    Compute SPYBenchmarkResult-equivalent stats for a target vs SPY.

    Args:
        target_hist: Monthly price history (Date, Close) for the stock/portfolio.
        spy_hist:    Monthly price history (Date, Close) for SPY, same range.

    Returns dict:
        normalized_target_series: list[float]  (rebased to 100 at start)
        normalized_spy_series:    list[float]
        beta:                     float | None
        alpha:                    float | None   (annualised %)
        cagr_target:              float | None   (%)
        cagr_spy:                 float | None   (%)
        probability_outperform:   float | None   (0..1)
        n_months:                 int
        error:                    str | None
    """
    def _empty(reason: str) -> dict[str, Any]:
        return {
            "normalized_target_series": [],
            "normalized_spy_series":    [],
            "beta":                     None,
            "alpha":                    None,
            "cagr_target":              None,
            "cagr_spy":                 None,
            "probability_outperform":   None,
            "n_months":                 0,
            "error":                    reason,
        }

    if target_hist is None or target_hist.empty:
        return _empty("No target price history provided")
    if spy_hist is None or spy_hist.empty:
        return _empty("No SPY price history provided")

    target = _prep(target_hist)
    spy = _prep(spy_hist)

    # Edge case: different lengths / date ranges → align/trim rather than crash.
    target, spy = _align(target, spy)
    if len(target) < 3 or len(spy) < 3:
        return _empty("Insufficient overlapping history between target and SPY")

    target_prices = target["Close"].values.astype(float)
    spy_prices = spy["Close"].values.astype(float)

    n_months = len(target_prices)
    n_years = max(n_months / MONTHS_PER_YEAR, 1 / MONTHS_PER_YEAR)

    cagr_target = _cagr(target_prices, n_years)
    cagr_spy = _cagr(spy_prices, n_years)

    # Edge case: flat/zero-variance series → guarded inside _beta_alpha (var check).
    target_rets = np.log(target_prices[1:] / target_prices[:-1])
    spy_rets = np.log(spy_prices[1:] / spy_prices[:-1])

    beta, alpha = _beta_alpha(target_rets, spy_rets, cagr_target, cagr_spy)

    probability_outperform = _bootstrap_probability_outperform(
        target_rets, spy_rets, horizon_months=horizon_months,
        n_sims=n_sims, seed=seed,
    )

    return {
        "normalized_target_series": _normalise(target_prices),
        "normalized_spy_series":    _normalise(spy_prices),
        "beta":                     round(beta, 4) if beta is not None else None,
        "alpha":                    round(alpha, 2) if alpha is not None else None,
        "cagr_target":              round(cagr_target, 2) if cagr_target is not None else None,
        "cagr_spy":                 round(cagr_spy, 2) if cagr_spy is not None else None,
        "probability_outperform":   probability_outperform,
        "n_months":                 n_months,
        "error":                    None,
    }
