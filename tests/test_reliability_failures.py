from unittest.mock import Mock

import pytest

from codes.core import redis_client
from codes.services import analysis_jobs, analysis_scheduler


def test_production_web_process_cannot_start_scheduler(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("ANALYSIS_BACKGROUND_JOBS", "1")
    monkeypatch.setenv("PROCESS_ROLE", "web")
    assert not analysis_scheduler._enabled()


def test_only_production_analysis_worker_role_owns_scheduler(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("ANALYSIS_BACKGROUND_JOBS", "1")
    monkeypatch.setenv("PROCESS_ROLE", "analysis-worker")
    assert analysis_scheduler._enabled()


def test_production_enqueue_fails_closed_without_redis(monkeypatch):
    monkeypatch.setattr(analysis_jobs, "get_redis", lambda: None)
    monkeypatch.setattr(analysis_jobs, "is_production", lambda: True)
    with pytest.raises(RuntimeError, match="Durable analysis queue unavailable"):
        analysis_jobs.enqueue({"type": "refresh-analysis", "symbol": "AAPL"})


def test_production_worker_fails_for_supervisor_without_redis(monkeypatch):
    monkeypatch.setattr(analysis_jobs, "get_redis", lambda: None)
    monkeypatch.setattr(analysis_jobs, "is_production", lambda: True)
    with pytest.raises(RuntimeError, match="Durable analysis queue unavailable"):
        analysis_jobs.work_forever()


def test_redis_retries_after_cooldown(monkeypatch):
    client = Mock()
    client.ping.return_value = True
    library = Mock()
    library.from_url.return_value = client
    monkeypatch.setattr(redis_client, "_REDIS_URL", "redis://example")
    monkeypatch.setattr(redis_client, "_redis_lib", library)
    monkeypatch.setattr(redis_client, "_client", False)
    monkeypatch.setattr(redis_client, "_failed_at", 100.0)
    monkeypatch.setattr(redis_client, "_RETRY_SECONDS", 5.0)
    monkeypatch.setattr(redis_client.time, "monotonic", lambda: 106.0)
    assert redis_client.get_redis() is client


def test_redis_failure_enters_bounded_cooldown(monkeypatch):
    library = Mock()
    library.from_url.side_effect = OSError("down")
    monkeypatch.setattr(redis_client, "_REDIS_URL", "redis://example")
    monkeypatch.setattr(redis_client, "_redis_lib", library)
    monkeypatch.setattr(redis_client, "_client", None)
    monkeypatch.setattr(redis_client.time, "monotonic", lambda: 50.0)
    assert redis_client.get_redis() is None
    assert redis_client._client is False
    assert redis_client._failed_at == 50.0
