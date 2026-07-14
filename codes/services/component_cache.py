"""Content-addressed model-component cache with Redis and memory fallback."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Callable

from codes.core.redis_client import get_redis, json_get, json_set

_memory: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()
_hits = 0
_misses = 0


def input_hash(value) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()[:20]


def cache_key(component: str, symbol: str, version: str, inputs) -> str:
    return f"analysis-component:{component}:{symbol.upper()}:{version}:{input_hash(inputs)}"


def get_or_compute(
    component: str,
    symbol: str,
    version: str,
    inputs,
    callback: Callable,
    *,
    ttl: int = 30 * 86400,
):
    global _hits, _misses
    key = cache_key(component, symbol, version, inputs)
    redis = get_redis()
    cached = json_get(redis, key) if redis is not None else None
    if cached is not None:
        _hits += 1
        return cached, True

    now = time.monotonic()
    with _lock:
        local = _memory.get(key)
        if local and local[0] > now:
            _hits += 1
            return local[1], True

    _misses += 1
    result = callback()
    with _lock:
        _memory[key] = (now + ttl, result)
    if redis is not None:
        json_set(redis, key, result, ex=ttl)
    return result, False


def stats() -> dict:
    total = _hits + _misses
    return {
        "hits": _hits,
        "misses": _misses,
        "hit_rate": round(_hits / total, 4) if total else None,
        "memory_entries": len(_memory),
    }
