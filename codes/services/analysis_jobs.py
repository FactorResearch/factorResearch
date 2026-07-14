"""Durable Redis analysis jobs with a local-development fallback."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor

from codes.core.redis_client import get_redis

_QUEUE = "jobs:analysis"
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
            pass
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


def work_forever() -> None:
    """Consume jobs in the designated background process."""
    while True:
        redis = get_redis()
        if redis is None:
            time.sleep(1)
            continue
        try:
            item = redis.blpop(_QUEUE, timeout=5)
            if not item:
                continue
            _key, raw = item
            job = json.loads(raw)
            attempts = int(job.get("attempts", 0))
            try:
                _dispatch(job)
            except Exception as exc:
                if attempts < 2:
                    job["attempts"] = attempts + 1
                    redis.rpush(_QUEUE, json.dumps(job))
                else:
                    redis.rpush(f"{_QUEUE}:dead", json.dumps({**job, "error": str(exc)}))
        except Exception as exc:
            print(f"Analysis job worker error: {exc}")
            time.sleep(1)


def health() -> dict:
    redis = get_redis()
    if redis is None:
        return {"backend": "local", "queued": 0, "dead_letter": 0}
    try:
        return {
            "backend": "redis",
            "queued": int(redis.llen(_QUEUE)),
            "dead_letter": int(redis.llen(f"{_QUEUE}:dead")),
        }
    except Exception:
        return {"backend": "unavailable", "queued": None, "dead_letter": None}
