"""Country/market configuration for the screener UI."""

DEFAULT_SCREENER_COUNTRY = "US"

SCREENER_COUNTRIES = [
    {
        "code": "US",
        "label": "United States",
        "short_label": "U.S.",
        "flag_src": "/assets/flags/us.svg",
        "row_values": {"US", "USA", "United States", "United States of America", ""},
    },
]


def get_screener_country(code: str | None) -> dict:
    """Return the configured screener country, falling back to the default."""
    countries = {country["code"]: country for country in SCREENER_COUNTRIES}
    return countries.get(code or DEFAULT_SCREENER_COUNTRY, countries[DEFAULT_SCREENER_COUNTRY])


def row_matches_country(row: dict, country_code: str | None) -> bool:
    """Future-ready row filter that keeps legacy rows in the U.S. universe."""
    country = get_screener_country(country_code)
    row_country = row.get("country") or row.get("country_code") or row.get("market") or ""
    return row_country in country["row_values"]
