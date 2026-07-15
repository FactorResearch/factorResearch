"""Durable Redis analysis jobs with a local-development fallback."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from codes.core.redis_client import get_redis
from codes.core.config import is_production

_QUEUE = "jobs:analysis"
_PROCESSING_QUEUE = f"{_QUEUE}:processing"
_local_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis-job")


def _dispatch(job: dict) -> None:
    if job.get("type") == "secondary-analysis":
        from codes.app_modules.analysis import _complete_secondary_analysis
        _complete_secondary_analysis(job["symbol"], job.get("shares_out"))
    elif job.get("type") == "refresh-analysis":
        from codes.app_modules.analysis import analyze_stock
        analyze_stock(job["symbol"], force_refresh=True, defer_secondary=True)


def enqueue(job: dict) -> None:
    redis = get_redis()
    if redis is not None:
        try:
            redis.rpush(_QUEUE, json.dumps(job, default=str))
            return
        except Exception:
            if is_production():
                raise RuntimeError("Durable analysis queue unavailable")
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
            return recovered
        recovered += 1


def consume_one(redis, timeout: int = 5) -> bool:
    raw = redis.brpoplpush(_QUEUE, _PROCESSING_QUEUE, timeout=timeout)
    if not raw:
        return False
    job = json.loads(raw)
    attempts = int(job.get("attempts", 0))
    try:
        _dispatch(job)
        redis.lrem(_PROCESSING_QUEUE, 1, raw)
    except Exception as exc:
        redis.lrem(_PROCESSING_QUEUE, 1, raw)
        if attempts < 2:
            redis.rpush(_QUEUE, json.dumps({**job, "attempts": attempts + 1}))
        else:
            redis.rpush(f"{_QUEUE}:dead", json.dumps({**job, "error": str(exc)}))
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
            consume_one(redis, timeout=1)
        except Exception as exc:
            print(f"Analysis job worker error: {exc}")
            if is_production():
                raise
            time.sleep(1)


def health() -> dict:
    redis = get_redis()
    if redis is None:
        return {"backend": "local" if not is_production() else "unavailable", "queued": 0, "processing": 0, "dead_letter": 0}
    try:
        return {
            "backend": "redis",
            "queued": int(redis.llen(_QUEUE)),
            "processing": int(redis.llen(_PROCESSING_QUEUE)),
            "dead_letter": int(redis.llen(f"{_QUEUE}:dead")),
        }
    except Exception:
        return {"backend": "unavailable", "queued": None, "dead_letter": None}
