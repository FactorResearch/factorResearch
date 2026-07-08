from unittest.mock import patch, MagicMock
import pandas as pd
from codes.engine import backtest


def _fake_wide(symbols, n=8):
    dates = pd.date_range("2024-01-31", periods=n, freq="ME")
    data = {s: [100 + i for i in range(n)] for s in symbols}
    data["SPY"] = [400 + i for i in range(n)]
    return pd.DataFrame(data, index=dates)


def test_score_filtered_uses_snapshot_when_sufficient_history():
    fake_universe = {
        "AAA": {"enhanced": {"composite_score": 40}, "composite": {}},
        "BBB": {"enhanced": {"composite_score": 40}, "composite": {}},
        "CCC": {"enhanced": {"composite_score": 40}, "composite": {}},
    }
    with patch("codes.engine.backtest._load_cached_universe", return_value=fake_universe), \
         patch("codes.engine.backtest._build_price_matrix", return_value=_fake_wide(["AAA", "BBB", "CCC"])), \
         patch("codes.engine.backtest.factor_snapshot.has_sufficient_history", return_value=True), \
         patch("codes.engine.backtest.factor_snapshot.get_factor_scores_asof",
               return_value={"graham": {"score": 90, "max_score": 100}}):
        result = backtest.score_filtered(min_score=50.0, years=1, rebalance_months=1)
    assert result["error"] is None
    assert result["look_ahead_bias"] is False  # snapshot path only, no fallback


def test_score_filtered_flags_bias_when_no_history():
    fake_universe = {
        "AAA": {"enhanced": {"composite_score": 80}, "composite": {}},
        "BBB": {"enhanced": {"composite_score": 20}, "composite": {}},
        "CCC": {"enhanced": {"composite_score": 90}, "composite": {}},
    }
    with patch("codes.engine.backtest._load_cached_universe", return_value=fake_universe), \
         patch("codes.engine.backtest._build_price_matrix", return_value=_fake_wide(["AAA", "BBB", "CCC"])), \
         patch("codes.engine.backtest.factor_snapshot.has_sufficient_history", return_value=False):
        result = backtest.score_filtered(min_score=50.0, years=1, rebalance_months=1)
    assert result["look_ahead_bias"] is True