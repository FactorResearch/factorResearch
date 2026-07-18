"""Acceptance tests for the managed background job queue."""

import threading
import time

from codes.services.adaptive_loading import AdaptiveJobStore, AsyncStatus, JobPriority, RetryPolicy


def _wait_for(store, job_id, owner, statuses):
    deadline = time.time() + 2
    while time.time() < deadline:
        snapshot = store.snapshot(job_id, owner=owner)
        if snapshot and snapshot.status in statuses:
            return snapshot
        time.sleep(0.005)
    raise AssertionError(f"job {job_id} did not reach {statuses}")


def test_interactive_jobs_outrank_maintenance_jobs(monkeypatch):
    monkeypatch.setattr("codes.services.adaptive_loading.get_redis", lambda: None)
    store = AdaptiveJobStore(max_workers=1)
    started = threading.Event()
    release = threading.Event()
    order = []

    def maintenance(_context):
        order.append("maintenance")
        started.set()
        release.wait(1)

    def interactive(_context):
        order.append("interactive")

    try:
        first = store.submit(
            operation="refresh",
            owner="system",
            dedupe_key="maintenance",
            work=maintenance,
            priority=JobPriority.MAINTENANCE,
        )
        assert started.wait(1)
        queued_maintenance = store.submit(
            operation="refresh",
            owner="system",
            dedupe_key="maintenance-2",
            work=lambda _context: order.append("maintenance-2"),
            priority=JobPriority.MAINTENANCE,
        )
        second = store.submit(
            operation="analysis",
            owner="u1",
            dedupe_key="interactive",
            work=interactive,
            priority=JobPriority.INTERACTIVE,
        )
        release.set()
        _wait_for(store, second.job_id, "u1", {AsyncStatus.SUCCESS})
        _wait_for(store, queued_maintenance.job_id, "system", {AsyncStatus.SUCCESS})
        assert order == ["maintenance", "interactive", "maintenance-2"]
        assert first.job_id != second.job_id
    finally:
        store.shutdown()


def test_every_job_has_bounded_timeout_and_dead_letter_isolated(monkeypatch):
    monkeypatch.setattr("codes.services.adaptive_loading.get_redis", lambda: None)
    store = AdaptiveJobStore(max_workers=1, retry_policy=RetryPolicy(base_delay_ms=1))
    started = threading.Event()

    def hangs(context):
        started.set()
        while True:
            context.raise_if_cancelled()
            time.sleep(0.002)

    try:
        timed = store.submit(
            operation="poison",
            owner="u1",
            dedupe_key="timeout",
            work=hangs,
            timeout_seconds=0.02,
            max_attempts=1,
        )
        assert started.wait(1)
        failed = _wait_for(store, timed.job_id, "u1", {AsyncStatus.ERROR})
        assert failed.stage == "Dead letter"
        assert [item.job_id for item in store.dead_letters(owner="u1")] == [timed.job_id]

        healthy = store.submit(
            operation="analysis",
            owner="u1",
            dedupe_key="healthy",
            work=lambda _context: {"ok": True},
        )
        assert _wait_for(store, healthy.job_id, "u1", {AsyncStatus.SUCCESS}).status == AsyncStatus.SUCCESS
    finally:
        store.shutdown()


def test_duplicate_submission_returns_same_job_and_health_exposes_heartbeat(monkeypatch):
    monkeypatch.setattr("codes.services.adaptive_loading.get_redis", lambda: None)
    store = AdaptiveJobStore(max_workers=1)
    try:
        first = store.submit(
            operation="export",
            owner="u1",
            dedupe_key="same-export",
            work=lambda _context: {"ok": True},
        )
        second = store.submit(
            operation="export",
            owner="u1",
            dedupe_key="same-export",
            work=lambda _context: {"different": True},
        )
        assert first.job_id == second.job_id
        _wait_for(store, first.job_id, "u1", {AsyncStatus.SUCCESS})
        health = store.health()
        assert health["dead_letter"] == 0
        assert health["status"] == "available"
    finally:
        store.shutdown()
