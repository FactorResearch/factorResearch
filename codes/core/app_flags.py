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


def get_current_flag() -> str:
    """Read the active flag; env var takes precedence over the JSON file."""
    override = os.environ.get("APP_FEATURE_FLAG")
    if override:
        flag = override.strip().upper()
        return flag if flag in _VALID_FLAGS else _DEFAULT_FLAG
    try:
        data = json.loads(_FLAG_FILE.read_text())
        flag = str(data.get("flag", _DEFAULT_FLAG)).strip().upper()
        return flag if flag in _VALID_FLAGS else _DEFAULT_FLAG
    except Exception:
        return _DEFAULT_FLAG


def is_internal_mode() -> bool:
    return get_current_flag() == "INTERNAL"


def billing_checks_disabled() -> bool:
    """True when the app should run at full access with no billing gates."""
    return is_internal_mode()