import threading

from codes.services import chart_service
from codes.workers import chart_worker


def setup_function():
    chart_service.clear_local_cache()


def test_chart_cache_key_is_versioned_and_hashes_config():
    req_a = chart_service.ChartRequest(
        ticker="AAPL",
        chart_type="price_history",
        period="10y",
        data_version="market-v1",
        analysis_version="analysis-1",
        chart_schema_version="chart-schema-v1",
        config={"formula": "close / revenue", "color": "blue"},
    )
    req_b = chart_service.ChartRequest(
        ticker="AAPL",
        chart_type="price_history",
        period="10y",
        data_version="market-v2",
        analysis_version="analysis-1",
        chart_schema_version="chart-schema-v1",
        config={"color": "blue", "formula": "close / revenue"},
    )

    key_a = chart_service.cache_key(req_a)
    key_b = chart_service.cache_key(req_b)

    assert key_a.startswith("chart:AAPL:price_history:10y:market-v1:analysis-1:chart-schema-v1:")
    assert key_b.startswith("chart:AAPL:price_history:10y:market-v2:analysis-1:chart-schema-v1:")
    assert "close / revenue" not in key_a
    assert key_a != key_b


def test_chart_service_reuses_cached_dataset():
    calls = {"count": 0}
    req = chart_service.ChartRequest("AAPL", "eps_history", analysis_version="analysis-1")

    def builder():
        calls["count"] += 1
        return {"series": [{"x": ["2025"], "y": [3.5]}]}

    first = chart_service.get_chart_dataset(req, builder)
    second = chart_service.get_chart_dataset(req, builder)

    assert first["meta"]["cache_hit"] is False
    assert second["meta"]["cache_hit"] is True
    assert first["series"] == second["series"]
    assert calls["count"] == 1


def test_analysis_version_change_uses_new_cache_entry():
    calls = {"count": 0}

    def builder():
        calls["count"] += 1
        return {"series": [{"x": ["2025"], "y": [calls["count"]]}]}

    req_1 = chart_service.ChartRequest("AAPL", "eps_history", analysis_version="analysis-1")
    req_2 = chart_service.ChartRequest("AAPL", "eps_history", analysis_version="analysis-2")

    chart_service.get_chart_dataset(req_1, builder)
    chart_service.get_chart_dataset(req_2, builder)

    assert calls["count"] == 2


def test_concurrent_requests_share_one_generation():
    calls = {"count": 0}
    barrier = threading.Barrier(5)
    req = chart_service.ChartRequest("AAPL", "price_history", analysis_version="analysis-1")
    results = []

    def builder():
        calls["count"] += 1
        return {"series": [{"x": ["2026-01-01"], "y": [100.0]}]}

    def run():
        barrier.wait()
        results.append(chart_service.get_chart_dataset(req, builder))

    threads = [threading.Thread(target=run) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls["count"] == 1
    assert len(results) == 5
    assert sum(1 for result in results if result["meta"]["cache_hit"] is False) == 1


def test_analysis_chart_dataset_normalizes_price_history():
    data = {
        "symbol": "AAPL",
        "analysis_version": "analysis-1",
        "price_history": [
            {"Date": "2026-01-01", "Close": 100},
            {"Date": "2026-01-02", "Close": 110},
        ],
        "spy_history": [
            {"Date": "2026-01-01", "Close": 50},
            {"Date": "2026-01-02", "Close": 55},
        ],
    }

    dataset = chart_service.get_analysis_chart_dataset(data, "price_history")

    assert dataset["series"][0]["name"] == "AAPL"
    assert dataset["series"][0]["y"] == [100.0, 110.00000000000001]
    assert dataset["series"][1]["name"] == "SPY"
    assert dataset["meta"]["cache_hit"] is False


def test_worker_precomputes_primary_analysis_charts(monkeypatch):
    data = {
        "symbol": "AAPL",
        "analysis_version": "analysis-1",
        "graham": {
            "eps_history": [{"year": 2025, "value": 3.5}],
            "div_history": [{"year": 2025, "value": 1_000_000}],
        },
        "price_history": [{"Date": "2026-01-01", "Close": 100}],
        "spy_history": [{"Date": "2026-01-01", "Close": 50}],
    }
    monkeypatch.setattr(chart_worker.db, "get_analysis", lambda ticker: data)

    first = chart_worker.precompute_analysis_charts("AAPL")
    second = chart_worker.precompute_analysis_charts("AAPL")

    assert len(first["generated"]) == 3
    assert first["errors"] == []
    assert all(item["cache_hit"] is True for item in second["generated"])
