"""Shared runtime configuration predicates."""

import os
from pathlib import Path


def is_production() -> bool:
    return os.environ.get("FLASK_ENV", "").lower() == "production"


def cache_root() -> Path:
    configured = os.environ.get("APP_CACHE_DIR")
    return Path(configured).expanduser().resolve() if configured else Path(__file__).resolve().parents[2] / ".cache"
