import numpy as np
import pandas as pd

from codes.models.comomentum import calc_comomentum
from codes.models import regime as regime_model


def _dates(n):
    return pd.date_range("2020-01-31", periods=n, freq="ME")


def test_comomentum_empty_universe():
    result = calc_comomentum([], {})
    assert result["signal"] == "NORMAL"
    assert result["percentile"] == 50.0
    assert result["raw_score"] is None
    assert result["error"] is not None


def test_comomentum_perfect_correlation():
    # 15 identical-trend series -> every rolling window has correlation ~1.0
    n = 15
    base = 100 * (1.02 ** np.arange(n))
    hist = {
        f"S{i}": pd.DataFrame({"Date": _dates(n), "Close": base})
        for i in range(4)
    }
    result = calc_comomentum(list(hist.keys()), hist, lookback_months=6)
    assert result["error"] is None
    assert result["percentile"] >= 90


def test_comomentum_zero_correlation():
    # First 30 months: identical (highly correlated) trend across symbols.
    # Last 6 months (the current lookback window): deliberately orthogonal
    # returns so the CURRENT correlation is the lowest in the history.
    rng = np.random.default_rng(42)
    n_hist = 30
    n_recent = 6
    n = n_hist + n_recent

    correlated = 100 * (1.01 ** np.arange(n_hist))
    prices = {}
    for i in range(4):
        tail = correlated[-1] * np.cumprod(1 + rng.normal(0, 0.05, n_recent) * (1 if i % 2 == 0 else -1))
        prices[f"S{i}"] = np.concatenate([correlated, tail])

    hist = {
        sym: pd.DataFrame({"Date": _dates(n), "Close": px})
        for sym, px in prices.items()
    }
    result = calc_comomentum(list(hist.keys()), hist, lookback_months=6)
    assert result["error"] is None
    assert result["percentile"] <= 30


def _bull_price_hist(n=15):
    """Steady, low-vol uptrend -> BULL_LOW_VOL regime."""
    prices = 100 * (1.02 ** np.arange(n))
    return pd.DataFrame({"Date": _dates(n), "Close": prices})


def test_regime_overlay_with_high_comomentum():
    price_hist = _bull_price_hist()

    baseline = regime_model.score(price_hist)
    assert baseline["regime"] in ("BULL_LOW_VOL", "BULL_HIGH_VOL")

    crowded = regime_model.score(
        price_hist, comomentum_result={"percentile": 90, "signal": "HIGH"}
    )
    assert crowded["comomentum_percentile"] == 90
    assert crowded["regime_multiplier"] == round(
        max(baseline["regime_multiplier"] - 0.10, 0.0), 4
    )