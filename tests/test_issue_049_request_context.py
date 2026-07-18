"""Acceptance tests for ISSUE_049 request and correlation propagation."""

import threading
import time

from codes.core.request_context import (
    ContextFilter,
    RequestContext,
    capture_context,
    context_scope,
    current_context,
)
from codes.services.adaptive_loading import AdaptiveJobStore, AsyncStatus
from codes.services.audit_journal import AuditJournal


def test_context_is_nested_thread_safe_and_restored() -> None:
    root = RequestContext.create(request_id="req-1", correlation_id="corr-1")
    seen: list[tuple[str, str, str | None]] = []
    with context_scope(root):
        child = root.child()
        with context_scope(child):
            seen.append((current_context().request_id, current_context().correlation_id, current_context().parent_operation_id))
        assert current_context() == root

        thread = threading.Thread(target=lambda: seen.append(("none", "none", current_context())))
        thread.start()
        thread.join()
    assert seen[0] == ("req-1", "corr-1", root.operation_id)
    assert seen[1] == ("none", "none", None)
    assert current_context() is None


def test_audit_events_inherit_request_and_operation_context(tmp_path) -> None:
    journal = AuditJournal(tmp_path / "events.jsonl")
    context = RequestContext.create(request_id="req-2", correlation_id="corr-2")
    with context_scope(context):
        event = journal.record("test", action="observe")
    assert event["request_id"] == "req-2"
    assert event["correlation_id"] == "corr-2"
    assert event["operation_id"] == context.operation_id


def test_job_boundary_captures_context_and_restores_worker_context(monkeypatch) -> None:
    monkeypatch.setattr("codes.services.adaptive_loading.get_redis", lambda: None)
    store = AdaptiveJobStore(max_workers=1)
    observed = []
    context = RequestContext.create(request_id="req-job", correlation_id="corr-job")

    try:
        with context_scope(context):
            snapshot = store.submit(
                operation="context-test",
                owner="u1",
                dedupe_key="one",
                work=lambda _job_context: observed.append(capture_context()),
            )
        deadline = time.time() + 2
        while time.time() < deadline and store.snapshot(snapshot.job_id, owner="u1").status != AsyncStatus.SUCCESS:
            time.sleep(0.005)
        assert observed[0].request_id == "req-job"
        assert observed[0].correlation_id == "corr-job"
        assert current_context() is None
    finally:
        store.shutdown()


def test_log_filter_adds_context_fields_without_user_payload() -> None:
    import logging

    record = logging.LogRecord("test", logging.INFO, __file__, 1, "message", (), None)
    context = RequestContext.create(request_id="req-log", correlation_id="corr-log")
    with context_scope(context):
        assert ContextFilter().filter(record)
    assert (record.request_id, record.correlation_id, record.operation_id) == (
        "req-log",
        "corr-log",
        context.operation_id,
    )


def test_http_response_exposes_request_and_correlation_ids() -> None:
    from codes.app import server

    response = server.test_client().get(
        "/privacy",
        headers={"X-Request-ID": "req-http", "X-Correlation-ID": "corr-http"},
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-http"
    assert response.headers["X-Correlation-ID"] == "corr-http"
    assert response.headers["X-Operation-ID"].startswith("op-")
