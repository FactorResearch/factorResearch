"""Per-account user settings helpers for profile and preference management."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re

from codes.data import db


DEFAULT_USER_SETTINGS = {
    "appearance": {
        "theme": "system",
    },
    "notifications": {
        "product_updates": True,
        "research_digest": False,
        "security_alerts": True,
    },
    "saved_screeners": [],
    "api_keys": [],
}

_THEMES = {"system", "light", "dark"}
_SCREENER_ID_RE = re.compile(r"[^a-z0-9]+")


def _deep_merge(base: dict, patch: dict) -> dict:
    merged = deepcopy(base)
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _normalize_theme(value: str | None) -> str:
    theme = str(value or "system").strip().lower()
    return theme if theme in _THEMES else "system"


def _normalize_notifications(value: dict | None) -> dict[str, bool]:
    current = dict((value or {}))
    defaults = DEFAULT_USER_SETTINGS["notifications"]
    return {
        key: bool(current[key]) if key in current else bool(defaults[key])
        for key in defaults
    }


def _normalize_saved_screener(item: dict) -> dict | None:
    name = str((item or {}).get("name") or "").strip()[:60]
    if not name:
        return None
    screener_id = str(item.get("id") or _SCREENER_ID_RE.sub("-", name.lower()).strip("-") or "screener")[:80]
    market = str(item.get("market") or "US").strip().upper()[:8]
    sector = str(item.get("sector") or "").strip()[:80]
    indexes = sorted({str(index).strip()[:40] for index in (item.get("indexes") or []) if str(index).strip()})[:20]
    saved_at = str(item.get("saved_at") or datetime.now(timezone.utc).isoformat())
    return {
        "id": screener_id,
        "name": name,
        "market": market,
        "sector": sector,
        "indexes": indexes,
        "saved_at": saved_at,
    }


def normalize_user_settings(settings: dict | None) -> dict:
    raw = _deep_merge(DEFAULT_USER_SETTINGS, settings or {})
    raw["appearance"] = {"theme": _normalize_theme((raw.get("appearance") or {}).get("theme"))}
    raw["notifications"] = _normalize_notifications(raw.get("notifications"))
    seen_ids: set[str] = set()
    screeners: list[dict] = []
    for item in raw.get("saved_screeners") or []:
        normalized = _normalize_saved_screener(item)
        if not normalized or normalized["id"] in seen_ids:
            continue
        seen_ids.add(normalized["id"])
        screeners.append(normalized)
    raw["saved_screeners"] = screeners
    raw["api_keys"] = list(raw.get("api_keys") or [])
    return raw


def get_user_settings(user_id: str) -> dict:
    return normalize_user_settings(db.get_user_settings(user_id))


def update_user_settings(user_id: str, patch: dict) -> dict:
    merged = normalize_user_settings(_deep_merge(get_user_settings(user_id), patch or {}))
    db.upsert_user_settings(user_id, merged)
    return merged


def set_theme(user_id: str, theme: str | None) -> dict:
    return update_user_settings(user_id, {"appearance": {"theme": _normalize_theme(theme)}})


def set_notifications(user_id: str, selected: list[str] | None) -> dict:
    selected_set = {str(value).strip() for value in (selected or [])}
    return update_user_settings(
        user_id,
        {
            "notifications": {
                "product_updates": "product_updates" in selected_set,
                "research_digest": "research_digest" in selected_set,
                "security_alerts": "security_alerts" in selected_set,
            }
        },
    )


def add_saved_screener(user_id: str, *, name: str, market: str, sector: str, indexes: list[str] | None) -> dict:
    current = get_user_settings(user_id)
    new_item = _normalize_saved_screener(
        {
            "name": name,
            "market": market,
            "sector": sector,
            "indexes": indexes or [],
        }
    )
    if not new_item:
        raise ValueError("Saved screener name is required.")
    existing = [item for item in current["saved_screeners"] if item["id"] != new_item["id"]]
    existing.insert(0, new_item)
    return update_user_settings(user_id, {"saved_screeners": existing[:20]})


def delete_saved_screener(user_id: str, screener_id: str | None) -> dict:
    target = str(screener_id or "").strip()
    current = get_user_settings(user_id)
    remaining = [item for item in current["saved_screeners"] if item["id"] != target]
    return update_user_settings(user_id, {"saved_screeners": remaining})
