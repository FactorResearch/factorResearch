"""Track analysis demand for priority-based background refresh."""

from __future__ import annotations

from collections import Counter
from threading import Lock

from codes.core.redis_client import get_redis

_KEY = "analysis:demand"
_local = Counter()
_lock = Lock()


def record(symbol: str, weight: float = 1.0) -> None:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return
    redis = get_redis()
    if redis is not None:
        try:
            redis.zincrby(_KEY, weight, symbol)
            redis.expire(_KEY, 90 * 86400)
            return
        except Exception:
            pass
    with _lock:
        _local[symbol] += weight


def popular(limit: int = 20) -> list[str]:
    redis = get_redis()
    if redis is not None:
        try:
            return [str(value) for value in redis.zrevrange(_KEY, 0, max(limit - 1, 0))]
        except Exception:
            pass
    with _lock:
        return [symbol for symbol, _count in _local.most_common(limit)]
