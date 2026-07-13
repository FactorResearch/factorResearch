"""Market provider registry.

Keeps market activation explicit so country releases can ship independently.
"""

from __future__ import annotations

import os

from .canada import CanadaProviderAdapter, is_canadian_symbol
from .canada_db import CanadaDatabaseDataSource


def _enabled_markets() -> set[str]:
    raw = os.environ.get("ENABLED_MARKETS", "US")
    return {part.strip().upper() for part in raw.split(",") if part.strip()}


def is_market_enabled(country_code: str) -> bool:
    return country_code.upper() in _enabled_markets()


def provider_for_symbol(symbol: str):
    if is_canadian_symbol(symbol):
        if not is_market_enabled("CA"):
            return None
        return CanadaProviderAdapter(CanadaDatabaseDataSource())
    return None


def configured_market_codes() -> list[str]:
    return sorted(_enabled_markets())
