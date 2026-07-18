"""Shared per-user rate limiting for callbacks and Flask routes."""

import threading
import time as _time

import flask

from codes.core.redis_client import get_redis, json_get, json_set
from codes.services.audit_journal import audit_journal

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

def check_rate_limit(  # noqa: C901 - Redis and local weighted paths share one reservation contract
    action: str,
    calls: int,
    period_seconds: int,
    key: str | None = None,
    *,
    cost: int = 1,
    priority: str = "essential",
):
    """Raise RateLimited if the caller exceeded `calls` in `period_seconds`.

    Key defaults to authenticated user id (if available) or remote IP.
    Backed by Redis (shared across workers/instances) when available,
    falling back to in-process memory for local dev without Redis.
    """
    if cost < 1:
        raise ValueError("rate-limit cost must be positive")
    if priority not in {"essential", "optional"}:
        raise ValueError("rate-limit priority must be essential or optional")
    if key is None:
        try:
            key = get_user_id()
        except Exception:
            key = flask.request.remote_addr if flask.request else "anon"
    store_key = f"rl:{action}:{key}"
    now = int(_time.time())
    reserve = _optional_reserve(calls) if priority == "optional" else 0
    effective_limit = calls - reserve
    if effective_limit < cost:
        raise ValueError("rate-limit budget must exceed the requested cost")

    r = get_redis()
    if r:
        weighted_key = f"{store_key}:weighted:{period_seconds}"
        if hasattr(r, "incrby"):
            used = int(r.incrby(weighted_key, int(cost)))
            if used == cost:
                r.expire(weighted_key, period_seconds + _RATE_LIMIT_TTL_PAD)
            if used > effective_limit:
                r.decrby(weighted_key, int(cost))
                _audit_rejection(action, key, cost, priority)
                raise RateLimited(retry_after=max(int(r.ttl(weighted_key)), 0))
            return
        entries = _weighted_entries(json_get(r, store_key) or [], now, period_seconds)
        used = sum(item["cost"] for item in entries)
        if used + cost > effective_limit:
            retry_after = period_seconds - (now - entries[0]["ts"]) if entries else period_seconds
            _audit_rejection(action, key, cost, priority)
            raise RateLimited(retry_after=retry_after)
        entries.append({"ts": now, "cost": cost})
        json_set(r, store_key, entries, ex=period_seconds + _RATE_LIMIT_TTL_PAD)
        return

    with _RATE_LIMIT_LOCK:
        entries = _weighted_entries(_RATE_LIMIT_STORE.get(store_key, []), now, period_seconds)
        used = sum(item["cost"] for item in entries)
        if used + cost > effective_limit:
            retry_after = period_seconds - (now - entries[0]["ts"]) if entries else period_seconds
            _RATE_LIMIT_STORE[store_key] = entries
            _audit_rejection(action, key, cost, priority)
            raise RateLimited(retry_after=retry_after)
        entries.append({"ts": now, "cost": cost})
        _RATE_LIMIT_STORE[store_key] = entries


def _optional_reserve(calls: int) -> int:
    """Reserve a configurable share of a budget for essential workflows."""
    from codes.core.config import get_config

    ratio = float(get_config("TRAFFIC_OPTIONAL_RESERVE_RATIO") or 0.2)
    return min(max(int(calls * ratio), 1), max(calls - 1, 0))


def _weighted_entries(entries: list, now: int, period_seconds: int) -> list[dict[str, int]]:
    """Normalize legacy timestamp entries and discard expired reservations."""
    result = []
    for entry in entries:
        if isinstance(entry, dict):
            timestamp, entry_cost = entry.get("ts"), entry.get("cost", 1)
        else:
            timestamp, entry_cost = entry, 1
        if isinstance(timestamp, (int, float)) and now - timestamp < period_seconds:
            result.append({"ts": int(timestamp), "cost": max(int(entry_cost), 1)})
    return result


def _audit_rejection(action: str, key: str, cost: int, priority: str) -> None:
    """Record a safe rate-limit decision without user or request payloads."""
    audit_journal.record(
        "traffic_control",
        action="throttle",
        component="rate_limit",
        outcome="denied",
        details={"action": action, "key_type": "user_or_ip", "cost": cost, "priority": priority},
    )

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
