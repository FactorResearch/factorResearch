"""Feature flag loader — ISSUE_032.

Reads the active flag from feature_flags.json at repo root (or
APP_FEATURE_FLAG env var override). Values: INTERNAL | BETA | V1 | V2 |
ENTERPRISE (mirrors codes.core.engine_contracts.FeatureFlag).

INTERNAL mode disables all billing/permission checks so the app runs at
full access. A git pre-push hook (.githooks/pre-push) refuses to push to
main while flag is INTERNAL or BETA.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_FLAG_FILE = Path(__file__).resolve().parents[2] / "feature_flags.json"
_DEFAULT_FLAG = "V1"
_VALID_FLAGS = {"INTERNAL", "BETA", "V1", "V2", "ENTERPRISE"}
_DEFAULT_MARKETS = {"US"}


def get_current_flag() -> str:
    """Read the active flag; env var takes precedence over the JSON file."""
    override = os.environ.get("APP_FEATURE_FLAG")
    if override:
        flag = override.strip().upper()
        return flag if flag in _VALID_FLAGS else _DEFAULT_FLAG
    data = _read_flags_file()
    flag = str(data.get("flag", _DEFAULT_FLAG)).strip().upper()
    return flag if flag in _VALID_FLAGS else _DEFAULT_FLAG


def get_enabled_markets() -> set[str]:
    """Return country/market codes enabled in feature_flags.json."""
    data = _read_flags_file()
    markets = data.get("markets")
    if not isinstance(markets, dict):
        return set(_DEFAULT_MARKETS)

    enabled = {
        str(code).strip().upper()
        for code, active in markets.items()
        if active is True
    }
    return enabled or set(_DEFAULT_MARKETS)


def is_market_enabled(country_code: str) -> bool:
    return country_code.strip().upper() in get_enabled_markets()


def _read_flags_file() -> dict:
    try:
        data = json.loads(_FLAG_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def is_internal_mode() -> bool:
    return get_current_flag() == "INTERNAL"


def billing_checks_disabled() -> bool:
    """True when the app should run at full access with no billing gates."""
    return is_internal_mode()
