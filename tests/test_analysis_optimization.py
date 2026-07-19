from unittest.mock import Mock, call
import json

from codes.services import stock_analysis as analysis
from codes.app_modules.tabs.analyze import (
    _client_analysis_payload,
    refresh_secondary_analysis,
    render_analysis_charts_on_demand,
    sync_secondary_analysis_polling,
)
from codes.app_modules.analysis_ui import _alternative_data_card, _insider_activity_card
from codes.services import performance_metrics
from codes.services import analysis_scheduler
from codes.services import analysis_demand


def test_client_payload_omits_chart_history():
    payload = _client_analysis_payload({
        "symbol": "AAPL",
        "price_history": {"Close": {"0": 1}},
        "spy_history": {"Close": {"0": 1}},
        "quality": {"score": 80},
    })

    assert payload == {"symbol": "AAPL", "quality": {"score": 80}}


def test_initial_analysis_payload_stays_below_contract_budget():
    payload = _client_analysis_payload({
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price_history": {"Close": {str(i): i for i in range(5000)}},
        "spy_history": {"Close": {str(i): i for i in range(5000)}},
        "quality": {"criteria": [{"label": "durable", "passed": True}] * 20},
    })

    assert len(json.dumps(payload).encode("utf-8")) <= 64 * 1024


def test_chart_callback_loads_history_from_server_cache(monkeypatch):
    cached = {"symbol": "AAPL", "price_history": {"Close": {"0": 1}}}
    load = Mock(return_value=cached)
    render = Mock(return_value=["chart"])
    monkeypatch.setattr(
        "codes.app_modules.tabs.analyze.stock_analysis.get_cached_analysis", load
    )
    monkeypatch.setattr("codes.app_modules.tabs.analyze.build_analysis_charts", render)

    assert render_analysis_charts_on_demand(1, {"symbol": "AAPL"}) == ["chart"]
    load.assert_called_once_with("AAPL")
    render.assert_called_once_with(cached)


def test_legacy_cache_is_served_and_marked_stale(monkeypatch):
    legacy = {"symbol": "AAPL"}
    monkeypatch.setattr(analysis, "_analysis_cache", {"AAPL": legacy})
    monkeypatch.setattr(analysis, "save_standard_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(analysis, "_attach_market_fear", lambda result: result)

    result = analysis.analyze_stock("AAPL")

    assert result["cache_hit"] is True
    assert result["cache_stale"] is True


def test_performance_snapshot_reports_percentiles(monkeypatch):
    monkeypatch.setattr(performance_metrics, "_samples", performance_metrics.deque(maxlen=500))
    monkeypatch.setattr(performance_metrics, "_payloads", performance_metrics.deque(maxlen=500))
    monkeypatch.setattr(performance_metrics, "_failures", performance_metrics.Counter())
    monkeypatch.setattr(performance_metrics, "_requests", performance_metrics.deque(maxlen=500))
    for duration in (10, 20, 30, 40, 50):
        performance_metrics.record_analysis(duration, duration <= 20)
    performance_metrics.record_payload(1000)
    performance_metrics.record_failure("provider:sec", TimeoutError())

    result = performance_metrics.snapshot()
    assert result["analysis"]["p50_ms"] == 30
    assert result["analysis"]["p95_ms"] == 50
    assert result["analysis"]["cache_hit_rate"] == 0.4
    assert result["analysis"]["avg_payload_bytes"] == 1000
    assert result["analysis"]["failures"] == {"provider:sec:TimeoutError": 1}


def test_background_maintenance_refreshes_shared_context_and_popular_symbols(monkeypatch):
    spy = Mock()
    fear = Mock()
    crowding = Mock()
    analyze = Mock()
    monkeypatch.setattr(analysis, "_get_spy_history_lazy", spy)
    monkeypatch.setattr(analysis, "_get_market_fear_result", fear)
    monkeypatch.setattr(analysis, "_get_comomentum_result", crowding)
    monkeypatch.setattr(analysis, "analyze_stock", analyze)
    monkeypatch.setattr(analysis_scheduler, "_popular_symbols", lambda: ["AAPL", "MSFT"])

    analysis_scheduler.run_maintenance_once()

    spy.assert_called_once()
    fear.assert_called_once()
    crowding.assert_called_once()
    assert analyze.call_args_list == [call("AAPL", force_refresh=True), call("MSFT", force_refresh=True)]


def test_local_demand_prioritizes_frequently_viewed_symbols(monkeypatch):
    monkeypatch.setattr(analysis_demand, "get_redis", lambda: None)
    monkeypatch.setattr(analysis_demand, "_local", analysis_demand.Counter())
    analysis_demand.record("MSFT")
    analysis_demand.record("AAPL", weight=3)

    assert analysis_demand.popular(2) == ["AAPL", "MSFT"]


def test_pending_secondary_cards_reserve_layout_space():
    data = {"secondary_status": "pending"}
    assert "Background enrichment" in str(_insider_activity_card(data))
    assert "Background enrichment" in str(_alternative_data_card(data))


def test_secondary_poll_rebuilds_content_when_enrichment_completes(monkeypatch):
    enriched = {"symbol": "AAPL", "secondary_status": "complete"}
    monkeypatch.setattr(
        "codes.app_modules.tabs.analyze.stock_analysis.get_cached_analysis",
        lambda _symbol: enriched,
    )
    monkeypatch.setattr("codes.app_modules.tabs.analyze._build_analysis_content", lambda result: [result["secondary_status"]])
    monkeypatch.setattr("codes.app_modules.tabs.analyze.permissions.can_access_feature", lambda *_args: None)
    monkeypatch.setattr("codes.app_modules.tabs.analyze.get_user_id", lambda: "test-user")

    content, payload = refresh_secondary_analysis(1, {"symbol": "AAPL", "secondary_status": "pending"})
    assert content == ["complete"]
    assert payload["secondary_status"] == "complete"


def test_secondary_polling_stops_when_no_deferred_work_remains():
    assert sync_secondary_analysis_polling(None) is True
    assert sync_secondary_analysis_polling({"secondary_status": "complete"}) is True
    assert sync_secondary_analysis_polling({"secondary_status": "pending"}) is False
