"""Feature-gated market registry and routing for the screener."""

from __future__ import annotations

from dataclasses import dataclass

from codes.core import app_flags

DEFAULT_SCREENER_MARKET = "US"


@dataclass(frozen=True, slots=True)
class ScreenerMarket:
    code: str
    slug: str
    label: str
    short_label: str
    flag_src: str
    row_values: frozenset[str]
    route_aliases: frozenset[str] = frozenset()

    @property
    def path(self) -> str:
        return f"/screener/{self.slug}"

# UI and routing metadata only. Provider, normalization, and release-quality
# behavior remain in codes.data.providers so market presentation cannot bypass
# the data-quality gates.
MARKET_REGISTRY: tuple[ScreenerMarket, ...] = (
    ScreenerMarket(
        code="US",
        slug="us",
        label="United States",
        short_label="U.S.",
        flag_src="/assets/flags/us.svg",
        row_values=frozenset({"", "us", "usa", "united states", "united states of america"}),
        route_aliases=frozenset({"usa", "united-states"}),
    ),
    ScreenerMarket(
        code="CA",
        slug="ca",
        label="Canada",
        short_label="Canada",
        flag_src="/assets/flags/ca.svg",
        row_values=frozenset({"ca", "can", "canada"}),
        route_aliases=frozenset({"can", "canada"}),
    ),
    ScreenerMarket(
        code="FR",
        slug="fr",
        label="France",
        short_label="France",
        flag_src="/assets/flags/fr.svg",
        row_values=frozenset({"fr", "fra", "france", "french republic"}),
        route_aliases=frozenset({"france", "euronext-paris", "paris"}),
    ),
)


def available_screener_markets() -> list[ScreenerMarket]:
    """Return release-enabled markets in stable display order."""
    enabled = app_flags.get_enabled_markets()
    markets = [market for market in MARKET_REGISTRY if market.code in enabled]
    if markets:
        return markets
    return [market for market in MARKET_REGISTRY if market.code == DEFAULT_SCREENER_MARKET]


def default_screener_market() -> ScreenerMarket:
    markets = available_screener_markets()
    return next(
        (market for market in markets if market.code == DEFAULT_SCREENER_MARKET),
        markets[0],
    )


def get_screener_market(value: str | None) -> ScreenerMarket:
    """Resolve an enabled market code, slug, or route alias."""
    key = str(value or "").strip().lower()
    for market in available_screener_markets():
        if key in {market.code.lower(), market.slug, *market.route_aliases}:
            return market
    return default_screener_market()


def market_from_path(pathname: str | None) -> ScreenerMarket:
    """Resolve `/screener/<market>` while retaining legacy code inputs."""
    raw = str(pathname or "").strip()
    if raw and "/" not in raw:
        return get_screener_market(raw)

    segments = [segment for segment in raw.split("/") if segment]
    if len(segments) >= 2 and segments[0].lower() == "screener":
        return get_screener_market(segments[1])
    return default_screener_market()


def market_path(value: str | None) -> str:
    return get_screener_market(value).path


def row_matches_market(row: dict, market_value: str | None) -> bool:
    """Match canonical market fields, retaining blank legacy U.S. rows."""
    market = get_screener_market(market_value)
    row_market = (
        row.get("market_code")
        or row.get("country_code")
        or row.get("country")
        or row.get("market")
        or ""
    )
    return str(row_market).strip().lower() in market.row_values
