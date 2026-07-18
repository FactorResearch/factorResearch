"""Durable Redis analysis jobs with a local-development fallback."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

from codes.core.config import is_production
from codes.core.redis_client import get_redis
from codes.domain.responses import JobResponse
from codes.services.audit_journal import audit_journal

_QUEUE = "jobs:analysis"
_MAINTENANCE_QUEUE = f"{_QUEUE}:maintenance"
_PROCESSING_QUEUE = f"{_QUEUE}:processing"
_HEARTBEAT_KEY = f"{_QUEUE}:heartbeat"
_local_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis-job")


def _prepare_job(job: dict) -> dict:
    """Attach the queue contract without changing caller-owned job payloads."""
    prepared = dict(job)
    prepared.setdefault("job_id", f"job-{uuid4().hex}")
    prepared.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    prepared.setdefault("attempts", 0)
    prepared.setdefault("max_attempts", 3)
    prepared.setdefault("timeout_seconds", 300)
    prepared.setdefault(
        "priority", "maintenance" if prepared.get("type") == "refresh-analysis" else "interactive"
    )
    return prepared


def _queue_name(job: dict) -> str:
    return _MAINTENANCE_QUEUE if job.get("priority") == "maintenance" else _QUEUE


def _dispatch(job: dict) -> None:
    if job.get("type") == "secondary-analysis":
        from codes.services.stock_analysis import _complete_secondary_analysis

        _complete_secondary_analysis(job["symbol"], job.get("shares_out"))
    elif job.get("type") == "refresh-analysis":
        from codes.services.stock_analysis import analyze_stock

        analyze_stock(job["symbol"], force_refresh=True, defer_secondary=True)


def enqueue(job: dict) -> None:
    job = _prepare_job(job)
    audit_journal.record(
        "job",
        action="enqueue",
        job_id=job["job_id"],
        ticker=str(job.get("symbol", "")),
        component="analysis_jobs",
        details={"type": job.get("type"), "priority": job.get("priority")},
    )
    redis = get_redis()
    if redis is not None:
        try:
            redis.rpush(_queue_name(job), json.dumps(job, default=str))
            return
        except Exception as exc:
            if is_production():
                raise RuntimeError("Durable analysis queue unavailable") from exc
    elif is_production():
        raise RuntimeError("Durable analysis queue unavailable")
    _local_executor.submit(_dispatch, job)


def enqueue_existing_stock_backfill(symbols: list[str] | None = None) -> int:
    """Queue an idempotent refresh for every previously analyzed stock."""
    if symbols is None:
        from codes.data import db

        symbols = db.list_analysis_tickers()
    normalized = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
    for symbol in normalized:
        enqueue({"type": "refresh-analysis", "symbol": symbol})
    return len(normalized)


def recover_interrupted_jobs(redis) -> int:
    """Return unacknowledged jobs to the queue when the sole worker starts."""
    recovered = 0
    while True:
        raw = redis.rpoplpush(_PROCESSING_QUEUE, _QUEUE)
        if raw is None:
            if recovered:
                audit_journal.record(
                    "job_recovery",
                    action="requeue_interrupted",
                    component="analysis_jobs",
                    details={"count": recovered},
                )
            return recovered
        recovered += 1


def consume_one(redis, timeout: int = 5) -> bool:
    raw = redis.brpoplpush(_QUEUE, _PROCESSING_QUEUE, timeout=0)
    if not raw:
        raw = redis.brpoplpush(_MAINTENANCE_QUEUE, _PROCESSING_QUEUE, timeout=timeout)
    if not raw:
        return False
    job = json.loads(raw)
    attempts = int(job.get("attempts", 0))
    try:
        _dispatch(job)
        redis.lrem(_PROCESSING_QUEUE, 1, raw)
        audit_journal.record(
            "job",
            action="complete",
            job_id=str(job.get("job_id", "")),
            ticker=str(job.get("symbol", "")),
            component="analysis_jobs",
        )
    except Exception as exc:
        redis.lrem(_PROCESSING_QUEUE, 1, raw)
        max_attempts = max(1, int(job.get("max_attempts", 3)))
        if attempts + 1 < max_attempts:
            retry = {**job, "attempts": attempts + 1, "last_error": type(exc).__name__}
            redis.rpush(_queue_name(retry), json.dumps(retry))
            audit_journal.record(
                "job",
                action="retry",
                job_id=str(job.get("job_id", "")),
                ticker=str(job.get("symbol", "")),
                component="analysis_jobs",
                severity="WARNING",
                outcome="retrying",
                details={"attempt": attempts + 1, "error": type(exc).__name__},
            )
        else:
            redis.rpush(
                f"{_QUEUE}:dead",
                json.dumps({**job, "error": type(exc).__name__, "terminal": True}),
            )
            audit_journal.record(
                "job",
                action="dead_letter",
                job_id=str(job.get("job_id", "")),
                ticker=str(job.get("symbol", "")),
                component="analysis_jobs",
                severity="ERROR",
                outcome="terminal_failure",
                details={"error": type(exc).__name__},
            )
    return True


def work_forever(stop_event: threading.Event | None = None) -> None:
    """Consume jobs in the designated background process."""
    stop_event = stop_event or threading.Event()
    recovered = False
    while not stop_event.is_set():
        redis = get_redis()
        if redis is None:
            if is_production():
                raise RuntimeError("Durable analysis queue unavailable")
            time.sleep(1)
            continue
        try:
            if not recovered:
                recover_interrupted_jobs(redis)
                recovered = True
            redis.set(_HEARTBEAT_KEY, datetime.now(timezone.utc).isoformat(), ex=30)
            consume_one(redis, timeout=1)
        except Exception as exc:
            print(f"Analysis job worker error: {exc}")
            if is_production():
                raise
            time.sleep(1)


def health() -> dict:
    redis = get_redis()
    if redis is None:
        return {
            "backend": "local" if not is_production() else "unavailable",
            "queued": 0,
            "processing": 0,
            "dead_letter": 0,
        }
    try:
        return {
            "backend": "redis",
            "queued": int(redis.llen(_QUEUE)) + int(redis.llen(_MAINTENANCE_QUEUE)),
            "processing": int(redis.llen(_PROCESSING_QUEUE)),
            "dead_letter": int(redis.llen(f"{_QUEUE}:dead")),
        }
    except Exception:
        return {"backend": "unavailable", "queued": None, "dead_letter": None}


def health_response() -> JobResponse:
    """Expose queue state without leaking the backing technology to clients."""
    state = health()
    backend = str(state.get("backend") or "unavailable")
    status = "AVAILABLE" if backend in {"local", "redis"} else "UNAVAILABLE"
    return JobResponse(
        status=status,
        queued=state.get("queued"),
        processing=state.get("processing"),
        failed=state.get("dead_letter"),
    )
