from unittest.mock import Mock

from codes.app_modules import analysis


def test_market_fear_failure_is_negative_cached(monkeypatch):
    monkeypatch.setattr(analysis, "_market_fear_cache", {"ts": 0.0, "result": None, "loaded": False})
    fetch = Mock(side_effect=RuntimeError("provider down"))
    monkeypatch.setattr(analysis.market_data, "get_market_fear_inputs", fetch)

    assert analysis._get_market_fear_result() is None
    assert analysis._get_market_fear_result() is None
    fetch.assert_called_once()


def test_empty_comomentum_universe_is_negative_cached(monkeypatch):
    monkeypatch.setattr(analysis, "_comomentum_cache", {"ts": 0.0, "result": None, "loaded": False})
    load = Mock(return_value=[])
    monkeypatch.setattr(analysis.screener, "get_screener_results", load)

    assert analysis._get_comomentum_result() is None
    assert analysis._get_comomentum_result() is None
    load.assert_called_once()


def test_failed_spy_fetch_retries_only_after_ttl(monkeypatch):
    monkeypatch.setattr(analysis, "_spy_history", None)
    monkeypatch.setattr(analysis, "_spy_history_loaded", False)
    monkeypatch.setattr(analysis, "_spy_history_ts", 0.0)
    fetch = Mock(side_effect=RuntimeError("provider down"))
    monkeypatch.setattr(analysis.api_fetcher, "get_price_history", fetch)

    assert analysis._get_spy_history_lazy() is None
    assert analysis._get_spy_history_lazy() is None
    fetch.assert_called_once()

    monkeypatch.setattr(analysis, "_spy_history_ts", analysis._time.time() - analysis._MARKET_FEAR_TTL - 1)
    assert analysis._get_spy_history_lazy() is None
    assert fetch.call_count == 2
