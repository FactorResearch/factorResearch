"""Tests for codes.models.spy_benchmark_model — pure math benchmark layer."""
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import numpy as np
import pandas as pd

from codes.models.spy_benchmark_model import compute_benchmark


def _monthly_dates(n: int) -> list[str]:
    return pd.date_range("2020-01-31", periods=n, freq="ME").strftime("%Y-%m-%d").tolist()


def _series(prices: list[float], n: int) -> pd.DataFrame:
    return pd.DataFrame({"Date": _monthly_dates(n), "Close": prices})


def test_matches_reference_beta_alpha_for_synthetic_series():
    # Deterministic synthetic series: target = SPY * 1.5x leverage (log-return space)
    rng = np.random.default_rng(0)
    n = 36
    spy_rets = rng.normal(0.006, 0.03, size=n - 1)
    spy_prices = [100.0]
    for r in spy_rets:
        spy_prices.append(spy_prices[-1] * np.exp(r))

    target_rets = spy_rets * 1.5
    target_prices = [50.0]
    for r in target_rets:
        target_prices.append(target_prices[-1] * np.exp(r))

    target_hist = _series(target_prices, n)
    spy_hist = _series(spy_prices, n)

    result = compute_benchmark(target_hist, spy_hist, n_sims=200)

    assert result["error"] is None
    # Reference calc via numpy directly
    ref_beta = np.cov(target_rets, spy_rets)[0, 1] / np.var(spy_rets, ddof=1)
    assert abs(result["beta"] - ref_beta) < 0.05
    assert result["normalized_target_series"][0] == 100.0
    assert result["normalized_spy_series"][0] == 100.0
    assert 0.0 <= result["probability_outperform"] <= 1.0


def test_different_length_series_are_aligned_not_crashed():
    target_hist = _series([100 + i for i in range(24)], 24)
    spy_hist = _series([200 + i * 0.5 for i in range(40)], 40)

    result = compute_benchmark(target_hist, spy_hist, n_sims=100)

    assert result["error"] is None
    assert result["n_months"] == 24  # trimmed to overlap
    assert len(result["normalized_target_series"]) == 24


def test_flat_zero_variance_series_does_not_divide_by_zero():
    n = 12
    target_hist = _series([100.0] * n, n)
    spy_hist = _series([200.0] * n, n)

    result = compute_benchmark(target_hist, spy_hist, n_sims=50)

    assert result["error"] is None
    assert result["beta"] is None  # zero variance in SPY returns → guarded, no crash
    assert result["cagr_target"] == 0.0
    assert result["cagr_spy"] == 0.0


def test_empty_history_returns_error_not_exception():
    empty = pd.DataFrame(columns=["Date", "Close"])
    non_empty = _series([100, 101, 102], 3)

    r1 = compute_benchmark(empty, non_empty)
    assert r1["error"] is not None

    r2 = compute_benchmark(non_empty, empty)
    assert r2["error"] is not None
