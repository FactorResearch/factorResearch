"""Lightweight product-funnel analytics backed by the existing usage table."""

from __future__ import annotations

from collections.abc import Mapping

from codes.data import db


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


def track_event(user_id: str, event_name: str, metadata: Mapping[str, object] | None = None) -> dict:
    if not user_id or not event_name:
        return {"usage_count": 0, "feature_usage": {}}
    return db.increment_usage(user_id, f"event:{event_name}", usage_key=_usage_key(metadata))
