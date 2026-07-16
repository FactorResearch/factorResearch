"""Shared per-user rate limiting for callbacks and Flask routes."""

import threading
import time as _time

import flask

from codes.core.redis_client import get_redis, json_get, json_set

from .session import get_user_id

# In-memory fallback only — used when Redis is unavailable (local dev).
# Under multi-worker gunicorn, Redis is authoritative so limits hold across workers.
_RATE_LIMIT_STORE: dict = {}
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_TTL_PAD = 5  # extra seconds so Redis key outlives the window

class RateLimited(Exception):
    def __init__(self, retry_after: int = 0):
        super().__init__("Rate limit exceeded")
        self.retry_after = int(retry_after)

def check_rate_limit(action: str, calls: int, period_seconds: int, key: str | None = None):
    """Raise RateLimited if the caller exceeded `calls` in `period_seconds`.

    Key defaults to authenticated user id (if available) or remote IP.
    Backed by Redis (shared across workers/instances) when available,
    falling back to in-process memory for local dev without Redis.
    """
    if key is None:
        try:
            key = get_user_id()
        except Exception:
            key = flask.request.remote_addr if flask.request else "anon"
    store_key = f"rl:{action}:{key}"
    now = int(_time.time())

    r = get_redis()
    if r:
        entries = json_get(r, store_key) or []
        entries = [ts for ts in entries if now - ts < period_seconds]
        if len(entries) >= calls:
            retry_after = period_seconds - (now - entries[0]) if entries else period_seconds
            raise RateLimited(retry_after=retry_after)
        entries.append(now)
        json_set(r, store_key, entries, ex=period_seconds + _RATE_LIMIT_TTL_PAD)
        return

    with _RATE_LIMIT_LOCK:
        entries = _RATE_LIMIT_STORE.get(store_key, [])
        entries = [ts for ts in entries if now - ts < period_seconds]
        if len(entries) >= calls:
            retry_after = period_seconds - (now - entries[0]) if entries else period_seconds
            _RATE_LIMIT_STORE[store_key] = entries
            raise RateLimited(retry_after=retry_after)
        entries.append(now)
        _RATE_LIMIT_STORE[store_key] = entries

def clear_rate_limits_for_user(user_id: str) -> None:
    r = get_redis()
    if r:
        try:
            for k in r.scan_iter(match=f"rl:*:{user_id}"):
                r.delete(k)
        except Exception:
            pass
    with _RATE_LIMIT_LOCK:
        for k in [k for k in _RATE_LIMIT_STORE if k.endswith(f":{user_id}")]:
            del _RATE_LIMIT_STORE[k]
