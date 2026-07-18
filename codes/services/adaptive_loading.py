"""Framework-neutral adaptive loading, retry, and resumable-job contracts."""

from __future__ import annotations

import itertools
import json
import queue
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import StrEnum
from hashlib import sha256
from threading import Event, Lock
from typing import Any

from codes.core.errors import classify_exception
from codes.core.redis_client import get_redis
from codes.core.request_context import RequestContext, capture_context, context_scope


class AsyncStatus(StrEnum):
    IDLE = "idle"
    DELAYED = "delayed"
    LOADING = "loading"
    PROGRESS = "progress"
    PARTIAL = "partial"
    SUCCESS = "success"
    EMPTY = "empty"
    STALE = "stale"
    ERROR = "error"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"


class JobPriority(StrEnum):
    """Execution classes; interactive work always outranks maintenance."""

    INTERACTIVE = "interactive"
    MAINTENANCE = "maintenance"


class LoadingTreatment(StrEnum):
    IMMEDIATE = "immediate-feedback"
    DELAYED = "delayed-scoped-loader"
    SCOPED = "scoped-skeleton"
    STAGED = "named-stage-progress"
    BACKGROUND = "resumable-background-job"


@dataclass(frozen=True)
class LoadingPolicy:
    delay_ms: int = 250
    minimum_visible_ms: int = 200
    scoped_after_ms: int = 1_000
    staged_after_ms: int = 3_000
    background_after_ms: int = 10_000

    def treatment_for(self, expected_ms: int) -> LoadingTreatment:
        if expected_ms < self.delay_ms:
            return LoadingTreatment.IMMEDIATE
        if expected_ms < self.scoped_after_ms:
            return LoadingTreatment.DELAYED
        if expected_ms < self.staged_after_ms:
            return LoadingTreatment.SCOPED
        if expected_ms < self.background_after_ms:
            return LoadingTreatment.STAGED
        return LoadingTreatment.BACKGROUND


PERMANENT_FAILURES = frozenset({"validation", "permission", "entitlement", "not_found"})


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_ms: int = 300
    max_delay_ms: int = 4_000
    jitter_ratio: float = 0.2

    def should_retry(self, failure_class: str, attempt: int) -> bool:
        return attempt < self.max_attempts and failure_class not in PERMANENT_FAILURES

    def delay_ms(self, attempt: int, *, random_value: float | None = None) -> int:
        base = min(self.max_delay_ms, self.base_delay_ms * (2 ** max(0, attempt - 1)))
        sample = random.random() if random_value is None else min(max(random_value, 0), 1)
        jitter = (sample * 2 - 1) * self.jitter_ratio
        return max(0, round(base * (1 + jitter)))


@dataclass(frozen=True)
class OperationPattern:
    operation: str
    expected_ms: int
    treatment: LoadingTreatment
    scope: str
    measurable: bool = False
    resumable: bool = False


DEFAULT_OPERATION_PATTERNS = (
    OperationPattern("tab-switch", 100, LoadingTreatment.IMMEDIATE, "control"),
    OperationPattern("cached-analysis", 700, LoadingTreatment.DELAYED, "analysis-section"),
    OperationPattern("quote-refresh", 2_000, LoadingTreatment.SCOPED, "metric-card"),
    OperationPattern("fresh-analysis", 7_000, LoadingTreatment.STAGED, "analysis-sections"),
    OperationPattern("screener-refresh", 8_000, LoadingTreatment.STAGED, "table-rows", True),
    OperationPattern("portfolio-load", 2_000, LoadingTreatment.SCOPED, "portfolio-content"),
    OperationPattern(
        "portfolio-simulation", 18_000, LoadingTreatment.BACKGROUND, "simulation", True, True
    ),
    OperationPattern(
        "factor-backtest", 18_000, LoadingTreatment.BACKGROUND, "backtest", True, True
    ),
    OperationPattern("chart-render", 2_000, LoadingTreatment.SCOPED, "chart", False),
    OperationPattern("authentication", 1_500, LoadingTreatment.SCOPED, "application-shell"),
    OperationPattern("billing", 2_500, LoadingTreatment.SCOPED, "billing-form"),
)


@dataclass(frozen=True)
class JobSnapshot:
    job_id: str
    operation: str
    owner: str
    status: AsyncStatus
    stage: str
    completed_units: int = 0
    total_units: int | None = None
    attempt: int = 1
    retryable: bool = False
    error_code: str | None = None
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    heartbeat_at: float = field(default_factory=time.time)
    timeout_seconds: float = 300.0
    priority: JobPriority = JobPriority.INTERACTIVE

    @property
    def percent(self) -> int | None:
        if not self.total_units:
            return None
        return min(100, round(self.completed_units / self.total_units * 100))

    def public_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "operation": self.operation,
            "status": self.status.value,
            "stage": self.stage,
            "completed_units": self.completed_units,
            "total_units": self.total_units,
            "percent": self.percent,
            "attempt": self.attempt,
            "retryable": self.retryable,
            "error_code": self.error_code,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "heartbeat_at": self.heartbeat_at,
            "timeout_seconds": self.timeout_seconds,
            "priority": self.priority.value,
        }


class JobContext:
    def __init__(self, store: AdaptiveJobStore, job_id: str, cancelled: Event) -> None:
        self._store = store
        self.job_id = job_id
        self._cancelled = cancelled

    def update(self, stage: str, *, completed_units: int | None = None) -> None:
        self._store._update(self.job_id, stage=stage, completed_units=completed_units)

    def raise_if_cancelled(self) -> None:
        if self._cancelled.is_set():
            raise JobCancelled


class JobCancelled(Exception):
    """Cooperative cancellation signal used only by resumable UI jobs."""


class AdaptiveJobStore:
    """Priority-aware, bounded, resumable jobs with isolated poison failures.

    The store keeps public history in Redis when available and otherwise keeps
    process-local history for development. Work is submitted to a priority
    queue so interactive jobs are selected before maintenance jobs. Timeout
    and cancellation are cooperative: job implementations must call
    ``JobContext.raise_if_cancelled`` at safe checkpoints.
    """

    def __init__(self, *, max_workers: int = 2, retry_policy: RetryPolicy | None = None) -> None:
        self._retry_policy = retry_policy or RetryPolicy()
        self._snapshots: dict[str, JobSnapshot] = {}
        self._results: dict[str, Any] = {}
        self._cancel: dict[str, Event] = {}
        self._dead_letters: dict[str, JobSnapshot] = {}
        self._job_config: dict[str, tuple[Callable[[JobContext], Any], float, int, float]] = {}
        self._job_contexts: dict[str, RequestContext | None] = {}
        self._pending: queue.PriorityQueue[tuple[int, int, str]] = queue.PriorityQueue()
        self._sequence = itertools.count()
        self._stopping = Event()
        self._workers = [
            threading.Thread(target=self._worker_loop, name=f"ui-job-{index}", daemon=True)
            for index in range(max(1, max_workers))
        ]
        self._lock = Lock()
        for worker in self._workers:
            worker.start()

    @staticmethod
    def stable_id(operation: str, owner: str, dedupe_key: str) -> str:
        digest = sha256(f"{operation}:{owner}:{dedupe_key}".encode()).hexdigest()[:24]
        return f"ui-{digest}"

    def submit(
        self,
        *,
        operation: str,
        owner: str,
        dedupe_key: str,
        work: Callable[[JobContext], Any],
        total_units: int | None = None,
        priority: JobPriority | str = JobPriority.INTERACTIVE,
        timeout_seconds: float = 300.0,
        max_attempts: int | None = None,
        heartbeat_seconds: float = 5.0,
    ) -> JobSnapshot:
        """Create or reuse a job and place it on the managed priority queue."""
        selected_priority = JobPriority(str(priority))
        if timeout_seconds <= 0 or heartbeat_seconds <= 0:
            raise ValueError("job timeout and heartbeat must be positive")
        attempts_limit = max_attempts if max_attempts is not None else self._retry_policy.max_attempts
        if attempts_limit < 1:
            raise ValueError("job max_attempts must be positive")
        job_id = self.stable_id(operation, owner, dedupe_key)
        with self._lock:
            existing = self._snapshots.get(job_id)
            if existing and existing.status in {
                AsyncStatus.LOADING,
                AsyncStatus.PROGRESS,
                AsyncStatus.SUCCESS,
            }:
                return existing
            snapshot = JobSnapshot(
                job_id,
                operation,
                owner,
                AsyncStatus.LOADING,
                "Queued",
                total_units=total_units,
                timeout_seconds=timeout_seconds,
                priority=selected_priority,
            )
            self._snapshots[job_id] = snapshot
            self._cancel[job_id] = Event()
            self._job_config[job_id] = (work, timeout_seconds, attempts_limit, heartbeat_seconds)
            self._job_contexts[job_id] = capture_context()
            self._persist(snapshot)
        priority_rank = 0 if selected_priority == JobPriority.INTERACTIVE else 1
        self._pending.put((priority_rank, next(self._sequence), job_id))
        return snapshot

    def _worker_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                _, _, job_id = self._pending.get(timeout=0.1)
            except queue.Empty:
                continue
            if not job_id:
                self._pending.task_done()
                continue
            with self._lock:
                config = self._job_config.get(job_id)
                snapshot = self._snapshots.get(job_id)
                job_context = self._job_contexts.get(job_id)
            if config and snapshot:
                with context_scope(job_context):
                    self._run(snapshot, config[0], config[1], config[2], config[3])
            self._pending.task_done()

    def _run(  # noqa: C901 - state transitions share one retry/timeout invariant
        self,
        initial: JobSnapshot,
        work: Callable[[JobContext], Any],
        timeout_seconds: float,
        max_attempts: int,
        heartbeat_seconds: float,
    ) -> None:
        job_id = initial.job_id
        context = JobContext(self, job_id, self._cancel[job_id])
        timed_out = Event()

        def monitor() -> None:
            started = time.monotonic()
            while not self._stopping.is_set() and not timed_out.is_set():
                if time.monotonic() - started >= timeout_seconds:
                    timed_out.set()
                    self._cancel[job_id].set()
                    self._update(job_id, stage="Timed out", retryable=True)
                    return
                self._update(job_id)
                time.sleep(min(heartbeat_seconds, max(0.01, timeout_seconds / 2)))

        monitor_thread = threading.Thread(target=monitor, name=f"heartbeat-{job_id}", daemon=True)
        monitor_thread.start()
        for attempt in range(1, max_attempts + 1):
            self._update(job_id, status=AsyncStatus.PROGRESS, stage="Running", attempt=attempt)
            try:
                result = work(context)
                if timed_out.is_set():
                    self._dead_letter(job_id)
                    return
                context.raise_if_cancelled()
                with self._lock:
                    self._results[job_id] = result
                self._update(job_id, status=AsyncStatus.SUCCESS, stage="Complete", retryable=False)
                return
            except JobCancelled:
                if timed_out.is_set():
                    self._dead_letter(job_id)
                    return
                self._update(
                    job_id, status=AsyncStatus.CANCELLED, stage="Cancelled", retryable=False
                )
                return
            except Exception as error:
                if timed_out.is_set():
                    self._dead_letter(job_id)
                    return
                structured_error = classify_exception(error)
                failure_class = getattr(error, "failure_class", "transient")
                retryable = attempt < max_attempts and failure_class not in PERMANENT_FAILURES
                if not retryable:
                    self._update(
                        job_id,
                        status=AsyncStatus.ERROR,
                        stage="Failed",
                        retryable=False,
                        error_code=structured_error.code,
                    )
                    self._dead_letter(job_id)
                    return
                self._update(
                    job_id, stage="Retrying", retryable=True, error_code=structured_error.code
                )
                time.sleep(self._retry_policy.delay_ms(attempt) / 1000)
        monitor_thread.join(timeout=0.1)

    def _dead_letter(self, job_id: str) -> None:
        with self._lock:
            snapshot = self._snapshots.get(job_id)
            if snapshot:
                failed = replace(snapshot, status=AsyncStatus.ERROR, stage="Dead letter", retryable=False)
                self._snapshots[job_id] = failed
                self._dead_letters[job_id] = failed
                self._persist(failed)

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            current = self._snapshots[job_id]
            if changes.get("completed_units") is None:
                changes.pop("completed_units", None)
            updated = replace(current, updated_at=time.time(), **changes)
            if "heartbeat_at" not in changes:
                updated = replace(updated, heartbeat_at=time.time())
            self._snapshots[job_id] = updated
            self._persist(updated)

    def dead_letters(self, *, owner: str | None = None) -> list[JobSnapshot]:
        """Return terminal poison jobs, optionally restricted to an owner."""
        with self._lock:
            values = list(self._dead_letters.values())
        return [item for item in values if owner is None or item.owner == owner]

    def health(self) -> dict[str, int | float | str]:
        """Expose queue depth and active worker heartbeat age."""
        now = time.time()
        with self._lock:
            heartbeats = [snapshot.heartbeat_at for snapshot in self._snapshots.values() if snapshot.status in {AsyncStatus.LOADING, AsyncStatus.PROGRESS}]
        return {
            "queued": self._pending.qsize(),
            "processing": len(heartbeats),
            "dead_letter": len(self._dead_letters),
            "oldest_heartbeat_age": max((now - value for value in heartbeats), default=0.0),
            "status": "stopping" if self._stopping.is_set() else "available",
        }

    def shutdown(self, *, wait: bool = True) -> None:
        """Stop accepting execution and optionally wait for active workers."""
        self._stopping.set()
        for _ in self._workers:
            self._pending.put((0, next(self._sequence), ""))
        if wait:
            for worker in self._workers:
                worker.join(timeout=2)

    def snapshot(self, job_id: str, *, owner: str) -> JobSnapshot | None:
        with self._lock:
            current = self._snapshots.get(job_id)
        if current is None:
            current = self._load(job_id)
        return current if current and current.owner == owner else None

    def result(self, job_id: str, *, owner: str) -> Any | None:
        snapshot = self.snapshot(job_id, owner=owner)
        if not snapshot or snapshot.status != AsyncStatus.SUCCESS:
            return None
        with self._lock:
            return self._results.get(job_id)

    def cancel(self, job_id: str, *, owner: str) -> bool:
        snapshot = self.snapshot(job_id, owner=owner)
        if not snapshot or snapshot.status not in {AsyncStatus.LOADING, AsyncStatus.PROGRESS}:
            return False
        self._cancel.get(job_id, Event()).set()
        return True

    @staticmethod
    def _redis_key(job_id: str) -> str:
        return f"ui-job:{job_id}"

    def _persist(self, snapshot: JobSnapshot) -> None:
        redis = get_redis()
        if redis is None:
            return
        try:
            redis.setex(
                self._redis_key(snapshot.job_id),
                86_400,
                json.dumps({**snapshot.public_dict(), "owner": snapshot.owner}),
            )
        except Exception:
            return

    def _load(self, job_id: str) -> JobSnapshot | None:
        redis = get_redis()
        if redis is None:
            return None
        try:
            raw = redis.get(self._redis_key(job_id))
            if not raw:
                return None
            data = json.loads(raw)
            data.pop("percent", None)
            data["status"] = AsyncStatus(data["status"])
            data["priority"] = JobPriority(data.get("priority", JobPriority.INTERACTIVE))
            return JobSnapshot(**data)
        except Exception:
            return None


jobs = AdaptiveJobStore()
