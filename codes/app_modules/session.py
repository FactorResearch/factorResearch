"""User/session and per-user portfolio-cache helpers."""

import os
import threading

import flask

from codes import auth
import codes.portfolio as portfolio_engine
from codes.core.redis_client import get_redis, json_get, json_set

# ── Screener ──────────────────────────────────────────────────────────────────
# Per-session portfolio cache (ISSUE-006) — scoped by Flask session id so one
# user's portfolio-ownership badges never leak into another user's screener view.
# _analysis_cache stays global: it's ticker-keyed, deterministic SEC/price data.
_portfolio_cache_by_session: dict = {}
_portfolio_cache_lock = threading.Lock()
_PORTFOLIO_CACHE_TTL = 600  # seconds before stale per-session portfolio caches are evicted

def get_user_id() -> str:
    """
    Get authenticated user_id (ISSUE_008).
    
    Returns the authenticated user_id from the auth system if available,
    otherwise falls back to a stable session UUID for local development.
    In production, authentication is required.
    """
    # Try to get authenticated user_id first
    user_id = auth.get_authenticated_user_id()
    if user_id:
        return user_id
    
    # Fallback to session UUID only in non-production environments.
    if os.environ.get("FLASK_ENV", "").lower() == "production":
        raise RuntimeError(
            "Authenticated user required in production. "
            "Set AUTH_PROVIDER and ensure auth is configured."
        )

    if "_uid" not in flask.session:
        import uuid
        flask.session["_uid"] = uuid.uuid4().hex
    return flask.session["_uid"]


def _evict_stale_portfolio_cache() -> None:
    import time as _t
    with _portfolio_cache_lock:
        stale = [sid for sid, entry in _portfolio_cache_by_session.items()
                 if _t.time() - entry.get("ts", 0) >= _PORTFOLIO_CACHE_TTL]
        for sid in stale:
            _portfolio_cache_by_session.pop(sid, None)


def invalidate_portfolio_cache() -> None:
    sid = get_user_id()
    r = get_redis()
    if r:
        try:
            r.delete(f"portfolio_symbols:{sid}")
        except Exception:
            pass
    with _portfolio_cache_lock:
        _portfolio_cache_by_session.pop(sid, None)

def get_portfolio_symbols() -> dict[str, list[str]]:
    import time as _t
    _evict_stale_portfolio_cache()
    sid = get_user_id()
    r = get_redis()
    redis_key = f"portfolio_symbols:{sid}"

    if r:
        cached = json_get(r, redis_key)
        if cached is not None:
            return cached
    else:
        with _portfolio_cache_lock:
            entry = _portfolio_cache_by_session.get(sid)
        if entry and _t.time() - entry["ts"] < 10:
            return entry["symbols"]

    result: dict[str, list[str]] = {}
    try:
        for pname in (portfolio_engine.list_portfolios(sid) or []):
            port = portfolio_engine.load_portfolio(sid, pname)
            if not port:
                continue
            for sym in (port.get("holdings") or {}).keys():
                if sym:
                    result.setdefault(sym, [])
                    if pname not in result[sym]:
                        result[sym].append(pname)
    except Exception:
        pass

    if r:
        json_set(r, redis_key, result, ex=10)
    else:
        with _portfolio_cache_lock:
            _portfolio_cache_by_session[sid] = {"symbols": result, "ts": _t.time()}
        stale_cutoff = _t.time() - 3600
        for stale_sid in [s for s, e in _portfolio_cache_by_session.items()
                          if e["ts"] < stale_cutoff]:
            _portfolio_cache_by_session.pop(stale_sid, None)
    return result
