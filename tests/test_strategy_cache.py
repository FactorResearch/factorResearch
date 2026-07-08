from unittest.mock import patch
from codes.engine import strategy_cache


def test_strategy_hash_stable_across_key_order():
    h1 = strategy_cache.strategy_hash({"graham": 0.5, "quality": 0.5})
    h2 = strategy_cache.strategy_hash({"quality": 0.5, "graham": 0.5})
    assert h1 == h2


def test_strategy_hash_differs_for_different_weights():
    h1 = strategy_cache.strategy_hash({"graham": 0.9, "quality": 0.1})
    h2 = strategy_cache.strategy_hash({"graham": 0.1, "quality": 0.9})
    assert h1 != h2


def test_get_or_run_backtest_reuses_cache():
    fake_result = {"cagr": 12.0, "error": None}
    with patch("codes.engine.strategy_cache.db.get_strategy_backtest", return_value=None) as get_mock, \
         patch("codes.engine.strategy_cache.db.set_strategy_backtest") as set_mock, \
         patch("codes.engine.strategy_cache.factor_backtest.run_factor_backtest", return_value=dict(fake_result)) as run_mock:
        result = strategy_cache.get_or_run_backtest({"graham": 1.0}, top_n=10, years=5)
    assert result["cache_hit"] is False
    run_mock.assert_called_once()
    set_mock.assert_called_once()

    with patch("codes.engine.strategy_cache.db.get_strategy_backtest",
               return_value={**fake_result, "cache_hit": False}) as get_mock2, \
         patch("codes.engine.strategy_cache.factor_backtest.run_factor_backtest") as run_mock2:
        result2 = strategy_cache.get_or_run_backtest({"graham": 1.0}, top_n=10, years=5)
    assert result2["cache_hit"] is True
    run_mock2.assert_not_called()