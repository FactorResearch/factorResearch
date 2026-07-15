"""Deduplicate identical concurrent work across threads and Redis workers."""

from __future__ import annotations

import json
import threading
import time
import weakref
from collections.abc import Callable
from typing import TypeVar

from codes.core.redis_client import get_redis

T = TypeVar("T")
_locks = weakref.WeakValueDictionary()
_local_results: dict[str, tuple[float, object]] = {}
_locks_guard = threading.Lock()
_MAX_LOCAL_KEYS = 1024


def _local_lock(key: str) -> threading.Lock:
    with _locks_guard:
        now = time.monotonic()
        expired = [name for name, entry in _local_results.items() if entry[0] <= now]
        for name in expired:
            _local_results.pop(name, None)
        while len(_local_results) >= _MAX_LOCAL_KEYS:
            _local_results.pop(next(iter(_local_results)))
        return _locks.setdefault(key, threading.Lock())


def run(key: str, callback: Callable[[], T], *, timeout: int = 90, result_ttl: int = 30) -> T:
    """Run callback once per key; followers receive the leader's JSON result."""
    local_lock = _local_lock(key)
    joined_active_flight = local_lock.locked()
    with local_lock:
        cached_local = _local_results.get(key)
        if joined_active_flight and cached_local and cached_local[0] > time.monotonic():
            return cached_local[1]  # type: ignore[return-value]
        redis = get_redis()
        if redis is None:
            result = callback()
            _local_results[key] = (time.monotonic() + result_ttl, result)
            return result

        result_key = f"singleflight:result:{key}"
        lock_key = f"singleflight:lock:{key}"
        try:
            cached = redis.get(result_key)
            if cached is not None:
                return json.loads(cached)
            acquired = bool(redis.set(lock_key, "1", nx=True, ex=timeout))
        except Exception:
            return callback()

        if acquired:
            try:
                result = callback()
                redis.set(result_key, json.dumps(result, default=str), ex=result_ttl)
                return result
            finally:
                try:
                    redis.delete(lock_key)
                except Exception:
                    pass

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                cached = redis.get(result_key)
                if cached is not None:
                    return json.loads(cached)
                if not redis.exists(lock_key):
                    break
            except Exception:
                break
            time.sleep(0.05)
        return callback()
