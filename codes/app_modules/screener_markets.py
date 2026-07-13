"""Country/market configuration for the screener UI."""

from codes.core import app_flags

DEFAULT_SCREENER_COUNTRY = "US"

_BASE_COUNTRIES = [
    {
        "code": "US",
        "label": "United States",
        "short_label": "U.S.",
        "flag_src": "/assets/flags/us.svg",
        "row_values": {"US", "USA", "United States", "United States of America", ""},
    },
]

_OPTIONAL_COUNTRIES = [
    {
        "code": "CA",
        "label": "Canada",
        "short_label": "Canada",
        "flag_src": "/assets/flags/ca.svg",
        "row_values": {"CA", "CAN", "Canada"},
        "requires_market": "CA",
    },
]


def _enabled_markets() -> set[str]:
    return app_flags.get_enabled_markets()


def _available_countries() -> list[dict]:
    enabled = _enabled_markets()
    countries = list(_BASE_COUNTRIES)
    countries.extend(
        country for country in _OPTIONAL_COUNTRIES
        if country.get("requires_market", "").upper() in enabled
    )
    return countries


SCREENER_COUNTRIES = _available_countries()


def get_screener_country(code: str | None) -> dict:
    """Return the configured screener country, falling back to the default."""
    countries = {country["code"]: country for country in _available_countries()}
    return countries.get(code or DEFAULT_SCREENER_COUNTRY, countries[DEFAULT_SCREENER_COUNTRY])


def row_matches_country(row: dict, country_code: str | None) -> bool:
    """Future-ready row filter that keeps legacy rows in the U.S. universe."""
    country = get_screener_country(country_code)
    row_country = row.get("country") or row.get("country_code") or row.get("market") or ""
    return row_country in country["row_values"]
