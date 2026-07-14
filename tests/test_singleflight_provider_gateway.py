import threading
import time
from unittest.mock import Mock

from codes.core import singleflight
from codes.services import provider_gateway


def test_singleflight_deduplicates_concurrent_local_work(monkeypatch):
    monkeypatch.setattr(singleflight, "get_redis", lambda: None)
    monkeypatch.setattr(singleflight, "_local_results", {})
    calls = 0
    results = []

    def work():
        nonlocal calls
        calls += 1
        time.sleep(0.03)
        return {"ok": True}

    threads = [threading.Thread(target=lambda: results.append(singleflight.run("same", work))) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls == 1
    assert results == [{"ok": True}] * 4


def test_provider_circuit_opens_after_repeated_failures(monkeypatch):
    monkeypatch.setattr(provider_gateway.singleflight, "run", lambda _key, callback, **_kwargs: callback())
    monkeypatch.setattr(provider_gateway, "_FAILURE_THRESHOLD", 2)
    monkeypatch.setattr(provider_gateway, "_states", {})
    monkeypatch.setattr(provider_gateway, "_semaphores", {})
    failing = Mock(side_effect=RuntimeError("down"))

    assert provider_gateway.call("sample", "one", failing, default=[]) == []
    assert provider_gateway.call("sample", "two", failing, default=[]) == []
    assert provider_gateway.call("sample", "three", failing, default=[]) == []
    assert failing.call_count == 2


def test_provider_health_exposes_breaker_state(monkeypatch):
    monkeypatch.setattr(provider_gateway, "_states", {"sec": {"failures": 1, "opened_at": 0.0}})
    assert provider_gateway.health()["sec"]["failures"] == 1
