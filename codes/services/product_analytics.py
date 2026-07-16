"""Product analytics service for async financial workflow events."""

from __future__ import annotations

import re
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor

from codes.core.ports import AnalyticsContext
from codes.data import analytics_db, db

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="product-analytics")
_EVENT_NAME = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
_SENSITIVE_METADATA_KEYS = {
    "symbol",
    "ticker",
    "portfolio_name",
    "compare",
    "query",
    "search_term",
    "email",
    "name",
    "shares",
    "price",
    "value",
    "formula",
    "weights",
    "account",
    "token",
    "key",
    "secret",
}


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
    path = _context.page_path()
    return normalize_page_path(path)


def normalize_page_path(path: str | None) -> str | None:
    if not path:
        return None
    clean_path = str(path).split("?", 1)[0]
    if re.fullmatch(r"/[A-Za-z]{1,6}/analyze/\d{8}", clean_path):
        return "/company/analyze/date"
    if re.fullmatch(r"/analyze/[A-Za-z]{1,6}(?:/.*)?", clean_path):
        return "/analyze/company"
    return clean_path[:160]


def sanitize_metadata(metadata: Mapping[str, object] | None) -> dict[str, object]:
    """Drop financial/account identifiers and bound privacy-safe dimensions."""
    sanitized: dict[str, object] = {}
    for key, value in (metadata or {}).items():
        normalized_key = str(key).strip().lower()[:64]
        if not normalized_key or normalized_key in _SENSITIVE_METADATA_KEYS:
            continue
        if isinstance(value, bool):
            sanitized[normalized_key] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            sanitized[normalized_key] = round(float(value), 2)
        elif isinstance(value, str):
            sanitized[normalized_key] = value[:80]
        elif isinstance(value, (list, tuple, set)):
            sanitized[f"{normalized_key}_count"] = len(value)
    return sanitized


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
        metadata=sanitize_metadata(metadata),
    )


def track_event(
    user_id: str,
    event_name: str,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if not event_name or not _EVENT_NAME.fullmatch(event_name) or not _tracking_enabled():
        return {"usage_count": 0, "feature_usage": {}}
    safe_metadata = sanitize_metadata(metadata)
    try:
        usage_value = db.increment_usage(
            user_id or _anonymous_id() or "anonymous",
            f"event:{event_name}",
            usage_key=_usage_key(safe_metadata),
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
        _EXECUTOR.submit(_record_event_sync, user_id, event_name, safe_metadata)
    except Exception:
        pass
    return usage
