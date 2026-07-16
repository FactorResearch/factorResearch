"""Product analytics service for async financial workflow events."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor

from codes.core.ports import AnalyticsContext
from codes.data import analytics_db, db

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="product-analytics")


class NullAnalyticsContext:
    """Context used by workers and tests that run outside a web request."""

    def anonymous_id(self) -> str | None:
        return None

    def authenticated_user_id(self) -> str | None:
        return None

    def page_path(self) -> str | None:
        return None

    def is_opted_out(self) -> bool:
        return False

    def set_opt_out(self, opt_out: bool) -> None:
        del opt_out


_context: AnalyticsContext = NullAnalyticsContext()


def configure_context(context: AnalyticsContext) -> None:
    """Inject the request-context adapter at the presentation composition root."""

    global _context
    _context = context


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
    return _context.anonymous_id()


def _page_path() -> str | None:
    return _context.page_path()


def _tracking_enabled() -> bool:
    return not _context.is_opted_out()


def set_tracking_opt_out(opt_out: bool) -> None:
    _context.set_opt_out(opt_out)


def is_tracking_opted_out() -> bool:
    return _context.is_opted_out()


def get_tracking_context() -> dict[str, object]:
    authenticated_user_id = _context.authenticated_user_id()
    anonymous_id = _context.anonymous_id()
    return {
        "tracking_enabled": _tracking_enabled(),
        "analytics_opt_out": is_tracking_opted_out(),
        "authenticated": bool(authenticated_user_id),
        "user_id": authenticated_user_id,
        "anonymous_id": anonymous_id,
    }


def _record_event_sync(
    user_id: str | None,
    event_name: str,
    metadata: Mapping[str, object] | None = None,
) -> None:
    if not _tracking_enabled() or not event_name:
        return
    analytics_db.insert_event(
        user_id=user_id,
        anonymous_id=_anonymous_id(),
        event_name=event_name,
        page_path=_page_path(),
        metadata=dict(metadata or {}),
    )


def track_event(
    user_id: str,
    event_name: str,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if not event_name or not _tracking_enabled():
        return {"usage_count": 0, "feature_usage": {}}
    try:
        usage_value = db.increment_usage(
            user_id or _anonymous_id() or "anonymous",
            f"event:{event_name}",
            usage_key=_usage_key(metadata),
        )
        usage = (
            usage_value
            if isinstance(usage_value, dict)
            else {
                "usage_count": 0,
                "feature_usage": {},
            }
        )
    except Exception:
        usage = {"usage_count": 0, "feature_usage": {}}
    try:
        _EXECUTOR.submit(_record_event_sync, user_id, event_name, metadata)
    except Exception:
        pass
    return usage
