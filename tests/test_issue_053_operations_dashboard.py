"""Acceptance tests for the fail-closed internal operations view."""

from codes.services import operations_dashboard
from codes.services.audit_journal import AuditJournal


def test_snapshot_is_read_only_and_searches_request_ids(monkeypatch, tmp_path):
    journal = AuditJournal(tmp_path / "events.jsonl")
    journal.record("request", request_id="req-53", details={"token": "secret"})
    monkeypatch.setattr(operations_dashboard, "audit_journal", journal)
    monkeypatch.setattr(operations_dashboard, "_health", lambda: {"state": "NORMAL"})
    monkeypatch.setattr(operations_dashboard.performance_metrics, "snapshot", lambda: {"requests": {}})
    monkeypatch.setattr(operations_dashboard.provider_gateway, "health", lambda: {})
    monkeypatch.setattr(operations_dashboard.analysis_jobs, "health", lambda: {"backend": "local"})
    monkeypatch.setattr(operations_dashboard.component_cache, "stats", lambda: {})
    monkeypatch.setattr(operations_dashboard.db, "pool_health", lambda: {})
    monkeypatch.setattr(operations_dashboard.analytics_db, "pool_health", lambda: {})

    result = operations_dashboard.snapshot(search="req-53")

    assert result["read_only"] is True
    assert result["events"][0]["request_id"] == "req-53"
    assert result["events"][0]["details"]["token"] == "[REDACTED]"


def test_snapshot_isolates_failed_optional_sources(monkeypatch):
    monkeypatch.setattr(operations_dashboard, "_health", lambda: {"state": "NORMAL"})
    monkeypatch.setattr(operations_dashboard.performance_metrics, "snapshot", lambda: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(operations_dashboard.provider_gateway, "health", lambda: {})
    monkeypatch.setattr(operations_dashboard.analysis_jobs, "health", lambda: {"backend": "local"})
    monkeypatch.setattr(operations_dashboard.component_cache, "stats", lambda: {})
    monkeypatch.setattr(operations_dashboard.db, "pool_health", lambda: {})
    monkeypatch.setattr(operations_dashboard.analytics_db, "pool_health", lambda: {})
    monkeypatch.setattr(operations_dashboard.audit_journal, "search", lambda **_: ())

    assert operations_dashboard.snapshot()["performance"]["status"] == "unavailable"
