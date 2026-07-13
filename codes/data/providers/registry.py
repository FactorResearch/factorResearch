"""Market provider registry.

Keeps market activation explicit so country releases can ship independently.
"""

from __future__ import annotations

from codes.core import app_flags
from codes.data import db

from .canada import CanadaProviderAdapter, is_canadian_symbol
from .canada_db import CanadaDatabaseDataSource, materialize_canada_screener_projection
from .canada_normalization import PUBLIC_CONFIDENCE
from .screener_projection import FUNDAMENTAL_PROJECTION_VERSION


MARKET_PROJECTION_BUILDERS = {
    "CA": materialize_canada_screener_projection,
}


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


def backfill_enabled_market_screener_projections() -> dict[str, int]:
    """Materialize rows for old verified imports without requiring re-import."""
    enabled_builders = {
        market: builder
        for market, builder in MARKET_PROJECTION_BUILDERS.items()
        if market in _enabled_markets()
    }
    stats = {"created": 0, "failed": 0}
    if not enabled_builders:
        return stats

    missing = db.list_market_symbols_missing_screener(
        tuple(enabled_builders),
        tuple(PUBLIC_CONFIDENCE),
        FUNDAMENTAL_PROJECTION_VERSION,
    )
    for item in missing:
        builder = enabled_builders.get(item["market_code"])
        if builder is None:
            continue
        try:
            if builder(item["symbol"]):
                stats["created"] += 1
        except Exception as exc:
            stats["failed"] += 1
            print(
                f"  [Market screener] projection failed for "
                f"{item['market_code']}:{item['symbol']}: {exc}"
            )
    return stats
