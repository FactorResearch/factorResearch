"""Market provider registry.

Keeps market activation explicit so country releases can ship independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from codes.core import app_flags
from codes.data import db

from .canada import CanadaProviderAdapter, is_canadian_symbol
from .canada_db import CanadaDatabaseDataSource, materialize_canada_screener_projection
from .canada_normalization import PUBLIC_CONFIDENCE, build_canada_scoring_facts
from .netherlands import NetherlandsProviderAdapter, is_netherlands_symbol
from .netherlands_db import NetherlandsDatabaseDataSource, materialize_netherlands_screener_projection
from .netherlands_normalization import build_netherlands_scoring_facts
from .screener_projection import FUNDAMENTAL_PROJECTION_VERSION


@dataclass(frozen=True, slots=True)
class MarketProviderRegistration:
    market_code: str
    market_name: str
    symbol_matcher: Callable[[str], bool]
    provider_factory: Callable[[], Any]
    scoring_builder: Callable[[Any, str], Any]
    projection_builder: Callable[[str], bool]


MARKET_PROVIDERS: tuple[MarketProviderRegistration, ...] = (
    MarketProviderRegistration(
        market_code="CA",
        market_name="Canada",
        symbol_matcher=is_canadian_symbol,
        provider_factory=lambda: CanadaProviderAdapter(CanadaDatabaseDataSource()),
        scoring_builder=build_canada_scoring_facts,
        projection_builder=materialize_canada_screener_projection,
    ),
    MarketProviderRegistration(
        market_code="NL",
        market_name="Netherlands",
        symbol_matcher=is_netherlands_symbol,
        provider_factory=lambda: NetherlandsProviderAdapter(NetherlandsDatabaseDataSource()),
        scoring_builder=build_netherlands_scoring_facts,
        projection_builder=materialize_netherlands_screener_projection,
    ),
)
MARKET_PROJECTION_BUILDERS = {
    registration.market_code: registration.projection_builder
    for registration in MARKET_PROVIDERS
}


def _enabled_markets() -> set[str]:
    return app_flags.get_enabled_markets()


def is_market_enabled(country_code: str) -> bool:
    return app_flags.is_market_enabled(country_code)


def provider_for_symbol(symbol: str):
    registration = _registration_for_symbol(symbol)
    if registration is None or not is_market_enabled(registration.market_code):
        return None
    return registration.provider_factory()


def scoring_facts_for_symbol(symbol: str) -> dict | None:
    """Return validated canonical facts for a recognized non-US symbol."""
    registration = _registration_for_symbol(symbol)
    if registration is None:
        return None
    _require_registration_enabled(registration)
    result = registration.scoring_builder(registration.provider_factory(), symbol)
    if result.can_score:
        return result.sec_facts
    details = "; ".join(issue.message for issue in result.quality_report.issues[:3])
    suffix = f" {details}" if details else ""
    raise ValueError(
        f"{registration.market_name} data is not verified enough to score.{suffix}"
    )


def require_symbol_market_enabled(symbol: str) -> None:
    """Reject disabled recognized markets before any cached result is returned."""
    registration = _registration_for_symbol(symbol)
    if registration is not None:
        _require_registration_enabled(registration)


def _registration_for_symbol(symbol: str) -> MarketProviderRegistration | None:
    return next(
        (registration for registration in MARKET_PROVIDERS if registration.symbol_matcher(symbol)),
        None,
    )


def _require_registration_enabled(registration: MarketProviderRegistration) -> None:
    if not is_market_enabled(registration.market_code):
        raise ValueError(f"{registration.market_name} market support is disabled.")


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
