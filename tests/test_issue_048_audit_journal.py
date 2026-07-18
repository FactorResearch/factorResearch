"""Acceptance tests for the ISSUE_048 operational event journal."""

import json
from pathlib import Path

from codes.services.audit_journal import AuditJournal
from codes.services.feature_management import FeatureContext, FeatureDefinition, FeatureManager


def test_events_are_append_only_structured_redacted_and_searchable(tmp_path: Path) -> None:
    journal = AuditJournal(tmp_path / "events.jsonl")
    first = journal.record(
        "provider",
        action="refresh",
        user_id="u1",
        request_id="req-1",
        correlation_id="corr-1",
        ticker="aapl",
        provider="sec",
        component="filings",
        severity="warning",
        details={"api_key": "do-not-store", "safe": "visible"},
    )
    journal.record("job", action="complete", user_id="u2", job_id="job-2")

    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    persisted = json.loads(lines[0])
    assert persisted["event_id"] == first["event_id"]
    assert persisted["ticker"] == "AAPL"
    assert persisted["details"] == {"api_key": "[REDACTED]", "safe": "visible"}
    assert journal.search(user_id="u1", ticker="AAPL")[0]["request_id"] == "req-1"
    assert journal.search(job_id="job-2")[0]["action"] == "complete"


def test_security_event_and_feature_change_are_journaled(monkeypatch, tmp_path: Path) -> None:
    from codes import security
    from codes.services import audit_journal as module
    from codes.services import feature_management

    journal = AuditJournal(tmp_path / "events.jsonl")
    monkeypatch.setattr(module, "audit_journal", journal)
    monkeypatch.setattr(security, "audit_journal", journal)
    monkeypatch.setattr(feature_management, "audit_journal", journal)
    security.audit_log_access("READ", "portfolio:1", "u1")

    definition = FeatureDefinition(
        name="journal-test",
        owner="platform",
        purpose="verify traceability",
        enabled=True,
        rollout_percent=100,
        removal_issue="ISSUE_048",
    )
    manager = FeatureManager(definition_file=tmp_path / "features.json")
    manager.set_definition(definition, actor="admin")

    events = journal.search(limit=10)
    assert {event["event_type"] for event in events} == {"access", "feature_policy"}
    assert any(event["actor_id"] == "admin" for event in events)
    assert manager.evaluate("journal-test", FeatureContext()).enabled


def test_search_rejects_unbounded_requests(tmp_path: Path) -> None:
    journal = AuditJournal(tmp_path / "events.jsonl")
    try:
        journal.search(limit=0)
    except ValueError as error:
        assert "limit" in str(error)
    else:
        raise AssertionError("unbounded audit searches must be rejected")
