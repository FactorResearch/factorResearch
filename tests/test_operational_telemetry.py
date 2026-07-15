from collections import Counter, deque

from codes.core.db_pool import ConnectionPool
from codes.services import performance_metrics


class Connection:
    closed = False
    broken = False

    def commit(self):
        pass

    def rollback(self):
        pass


def test_request_metrics_use_route_templates_and_are_bounded(monkeypatch):
    monkeypatch.setattr(performance_metrics, "_requests", deque(maxlen=3))
    for index in range(10):
        performance_metrics.record_request("/analyze/<ticker>", "GET", 500 if index == 9 else 200, index)
    result = performance_metrics.snapshot()["requests"]
    assert result["count"] == 3
    assert result["error_rate"] == round(1 / 3, 4)
    assert set(result["routes"]) == {"GET /analyze/<ticker> 2xx", "GET /analyze/<ticker> 5xx"}


def test_failure_labels_are_bounded(monkeypatch):
    monkeypatch.setattr(performance_metrics, "_failures", Counter())
    monkeypatch.setattr(performance_metrics, "_MAX_FAILURE_KEYS", 3)
    for index in range(10):
        performance_metrics.record_failure(f"component-{index}", RuntimeError())
    assert len(performance_metrics._failures) == 3


def test_pool_stats_expose_counts_without_connection_details():
    pool = ConnectionPool(Connection, max_size=2)
    with pool.connection():
        stats = pool.stats()
        assert stats == {"created": 1, "available": 0, "in_use": 1, "max_size": 2, "utilization": 0.5}
    assert pool.stats()["available"] == 1


def test_app_adds_sanitized_request_id_and_template_metric(monkeypatch):
    from codes.app import server

    monkeypatch.setattr(performance_metrics, "_requests", deque(maxlen=500))
    response = server.test_client().get("/privacy?secret=ticker", headers={"X-Request-ID": "bad value with spaces"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "bad value with spaces"
    assert "secret" not in str(performance_metrics.snapshot()["requests"]["routes"])
