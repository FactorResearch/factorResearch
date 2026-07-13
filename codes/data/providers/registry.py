"""Market provider registry.

Keeps market activation explicit so country releases can ship independently.
"""

from __future__ import annotations

from codes.core import app_flags

from .canada import CanadaProviderAdapter, is_canadian_symbol
from .canada_db import CanadaDatabaseDataSource


def _enabled_markets() -> set[str]:
    return app_flags.get_enabled_markets()


def is_market_enabled(country_code: str) -> bool:
    return app_flags.is_market_enabled(country_code)


def provider_for_symbol(symbol: str):
    if is_canadian_symbol(symbol):
        if not is_market_enabled("CA"):
            return None
        return CanadaProviderAdapter(CanadaDatabaseDataSource())
    return None


def configured_market_codes() -> list[str]:
    return sorted(_enabled_markets())
