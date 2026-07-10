"""Product analytics service for async financial workflow events."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
import os

import flask

from codes.data import analytics_db
from codes.data import db

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="product-analytics")
_SESSION_OPT_OUT_KEY = "analytics_opt_out"


def _usage_key(metadata: Mapping[str, object] | None) -> str:
    if not metadata:
        return "all"
    parts = []
    for key in sorted(metadata):
        value = metadata[key]
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    return "|".join(parts) or "all"


def _anonymous_id() -> str | None:
    if not flask.has_request_context():
        return None
    return flask.session.get("_uid") or flask.session.get("_authenticated_user_id")


def _page_path() -> str | None:
    if not flask.has_request_context():
        return None
    try:
        return flask.request.path
    except Exception:
        return None


def _tracking_enabled() -> bool:
    if os.environ.get("ANALYTICS_OPT_OUT", "").lower() in {"1", "true", "yes"}:
        return False
    if flask.has_request_context() and flask.session.get(_SESSION_OPT_OUT_KEY):
        return False
    return True


def set_tracking_opt_out(opt_out: bool) -> None:
    if not flask.has_request_context():
        return
    flask.session[_SESSION_OPT_OUT_KEY] = bool(opt_out)


def is_tracking_opted_out() -> bool:
    if not flask.has_request_context():
        return False
    return bool(flask.session.get(_SESSION_OPT_OUT_KEY))


def _record_event_sync(user_id: str | None, event_name: str, metadata: Mapping[str, object] | None = None) -> None:
    if not _tracking_enabled() or not event_name:
        return
    analytics_db.insert_event(
        user_id=user_id,
        anonymous_id=_anonymous_id(),
        event_name=event_name,
        page_path=_page_path(),
        metadata=dict(metadata or {}),
    )


def track_event(user_id: str, event_name: str, metadata: Mapping[str, object] | None = None) -> dict:
    if not event_name or not _tracking_enabled():
        return {"usage_count": 0, "feature_usage": {}}
    try:
        usage = db.increment_usage(
            user_id or _anonymous_id() or "anonymous",
            f"event:{event_name}",
            usage_key=_usage_key(metadata),
        )
    except Exception:
        usage = {"usage_count": 0, "feature_usage": {}}
    try:
        _EXECUTOR.submit(_record_event_sync, user_id, event_name, metadata)
    except Exception:
        pass
    return usage
