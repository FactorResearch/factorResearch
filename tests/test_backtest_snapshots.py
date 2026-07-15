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
         patch("codes.engine.backtest.factor_snapshot.load_history", return_value={}), \
         patch("codes.engine.backtest.factor_snapshot.history_has_sufficient_dates", return_value=True), \
         patch("codes.engine.backtest.factor_snapshot.history_scores_asof",
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
         patch("codes.engine.backtest.factor_snapshot.load_history", return_value={}), \
         patch("codes.engine.backtest.factor_snapshot.history_has_sufficient_dates", return_value=False):
        result = backtest.score_filtered(min_score=50.0, years=1, rebalance_months=1)
    assert result["look_ahead_bias"] is True


def test_score_filtered_caps_ranked_holdings_at_top_n():
    symbols = ["AAA", "BBB", "CCC", "DDD"]
    universe = {symbol: {"enhanced": {"composite_score": score}} for symbol, score in zip(symbols, [90, 80, 70, 60])}
    with patch("codes.engine.backtest._load_cached_universe", return_value=universe), \
         patch("codes.engine.backtest._build_price_matrix", return_value=_fake_wide(symbols)), \
         patch("codes.engine.backtest.factor_snapshot.load_history", return_value={}), \
         patch("codes.engine.backtest.factor_snapshot.history_has_sufficient_dates", return_value=False):
        result = backtest.score_filtered(min_score=50, top_n=3, years=1, rebalance_months=1)
    assert result["final_symbols"] == ["AAA", "BBB", "CCC"]
