import threading
import time

from codes.app_modules.design_system.states import (
    background_job_status,
    chart_skeleton,
    partial_data_notice,
    section_error,
    stale_data_notice,
    table_skeleton,
)
from codes.services import performance_metrics
from codes.services.adaptive_loading import (
    AdaptiveJobStore,
    AsyncStatus,
    LoadingPolicy,
    LoadingTreatment,
    RetryPolicy,
)


def test_loading_policy_selects_proportional_treatments():
    policy = LoadingPolicy()
    assert policy.treatment_for(100) == LoadingTreatment.IMMEDIATE
    assert policy.treatment_for(500) == LoadingTreatment.DELAYED
    assert policy.treatment_for(2_000) == LoadingTreatment.SCOPED
    assert policy.treatment_for(5_000) == LoadingTreatment.STAGED
    assert policy.treatment_for(15_000) == LoadingTreatment.BACKGROUND


def test_retry_policy_is_bounded_jittered_and_skips_permanent_failures():
    policy = RetryPolicy(max_attempts=3, base_delay_ms=100, jitter_ratio=0.2)
    assert policy.should_retry("transient", 1)
    assert not policy.should_retry("transient", 3)
    assert not policy.should_retry("permission", 1)
    assert policy.delay_ms(1, random_value=0) == 80
    assert policy.delay_ms(1, random_value=1) == 120
    assert policy.delay_ms(2, random_value=0.5) == 200


def _wait_for(store, job_id, owner, terminal):
    deadline = time.time() + 2
    while time.time() < deadline:
        snapshot = store.snapshot(job_id, owner=owner)
        if snapshot and snapshot.status in terminal:
            return snapshot
        time.sleep(0.005)
    raise AssertionError("job did not reach a terminal state")


def test_job_is_stable_deduplicated_progressive_and_resumable(monkeypatch):
    monkeypatch.setattr("codes.services.adaptive_loading.get_redis", lambda: None)
    store = AdaptiveJobStore(max_workers=1, retry_policy=RetryPolicy(base_delay_ms=1))
    release = threading.Event()

    def work(context):
        context.update("Fetching", completed_units=1)
        release.wait(1)
        context.update("Rendering", completed_units=2)
        return {"ok": True}

    first = store.submit(
        operation="backtest", owner="u1", dedupe_key="same", work=work, total_units=2
    )
    second = store.submit(
        operation="backtest", owner="u1", dedupe_key="same", work=work, total_units=2
    )
    assert first.job_id == second.job_id
    assert store.snapshot(first.job_id, owner="someone-else") is None
    release.set()
    complete = _wait_for(store, first.job_id, "u1", {AsyncStatus.SUCCESS})
    assert complete.percent == 100
    assert store.result(first.job_id, owner="u1") == {"ok": True}


def test_job_retries_transient_failure_and_stops_on_permanent(monkeypatch):
    monkeypatch.setattr("codes.services.adaptive_loading.get_redis", lambda: None)
    store = AdaptiveJobStore(
        max_workers=1, retry_policy=RetryPolicy(max_attempts=2, base_delay_ms=1, jitter_ratio=0)
    )
    attempts = []

    def flaky(_context):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("temporary")
        return "done"

    snapshot = store.submit(operation="chart", owner="u1", dedupe_key="retry", work=flaky)
    complete = _wait_for(store, snapshot.job_id, "u1", {AsyncStatus.SUCCESS})
    assert complete.attempt == 2
    assert len(attempts) == 2

    class PermissionFailure(RuntimeError):
        failure_class = "permission"

    denied = store.submit(
        operation="chart",
        owner="u1",
        dedupe_key="denied",
        work=lambda _context: (_ for _ in ()).throw(PermissionFailure()),
    )
    failed = _wait_for(store, denied.job_id, "u1", {AsyncStatus.ERROR})
    assert failed.attempt == 1
    assert not failed.retryable


def test_job_supports_cooperative_cancel(monkeypatch):
    monkeypatch.setattr("codes.services.adaptive_loading.get_redis", lambda: None)
    store = AdaptiveJobStore(max_workers=1, retry_policy=RetryPolicy(base_delay_ms=1))
    started = threading.Event()

    def work(context):
        started.set()
        while True:
            context.raise_if_cancelled()
            time.sleep(0.002)

    snapshot = store.submit(operation="simulation", owner="u1", dedupe_key="cancel", work=work)
    assert started.wait(1)
    assert store.cancel(snapshot.job_id, owner="u1")
    cancelled = _wait_for(store, snapshot.job_id, "u1", {AsyncStatus.CANCELLED})
    assert cancelled.status == AsyncStatus.CANCELLED


def test_shared_states_reserve_space_and_expose_local_actions():
    assert "ds-skeleton-frame--chart" in chart_skeleton().className
    assert "ds-skeleton-frame--table" in table_skeleton().className
    assert section_error("failed", retry_id="retry", technical_id="trace") is not None
    assert stale_data_notice() is not None
    assert partial_data_notice(["history"]) is not None
    assert (
        background_job_status(
            {"job_id": "j1", "status": "progress", "stage": "Run"}, cancel_id="cancel"
        )
        is not None
    )


def test_ui_metrics_report_latency_outcomes_and_no_input_values(monkeypatch):
    monkeypatch.setattr(
        performance_metrics, "_ui_operations", __import__("collections").deque(maxlen=20)
    )
    performance_metrics.record_ui_operation(
        "fresh-analysis",
        1200,
        outcome="partial",
        section="charts",
        retries=1,
        stale_fallback=True,
        first_useful_ms=350,
    )
    result = performance_metrics.snapshot()["ui_operations"]
    assert result["p75_ms"] == 1200
    assert result["first_useful_p75_ms"] == 350
    assert result["outcomes"] == {"partial": 1}
    assert result["retry_count"] == 1
    assert result["stale_fallback_count"] == 1
