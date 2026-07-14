import json

from codes.app_modules import screener_markets
from codes.core import app_flags


def _set_enabled_markets(monkeypatch, tmp_path, markets):
    flag_file = tmp_path / "feature_flags.json"
    flag_file.write_text(json.dumps({"flag": "INTERNAL", "markets": markets}))
    monkeypatch.setattr(app_flags, "_FLAG_FILE", flag_file)


def test_market_routes_resolve_from_feature_gated_registry(monkeypatch, tmp_path):
    _set_enabled_markets(monkeypatch, tmp_path, {"US": True, "CA": True})

    assert [market.code for market in screener_markets.available_screener_markets()] == ["US", "CA"]
    assert screener_markets.market_from_path("/screener/us").code == "US"
    assert screener_markets.market_from_path("/screener/ca").code == "CA"
    assert screener_markets.market_from_path("/screener/canada").code == "CA"
    assert screener_markets.market_path("CA") == "/screener/ca"


def test_disabled_or_unknown_market_routes_use_enabled_default(monkeypatch, tmp_path):
    _set_enabled_markets(monkeypatch, tmp_path, {"US": True, "CA": False})

    assert screener_markets.market_from_path("/screener/ca").code == "US"
    assert screener_markets.market_from_path("/screener/fr").code == "US"
    assert screener_markets.market_from_path("/").code == "US"


def test_market_row_matching_prefers_canonical_market_fields(monkeypatch, tmp_path):
    _set_enabled_markets(monkeypatch, tmp_path, {"US": True, "CA": True})

    assert screener_markets.row_matches_market({"market_code": "CA"}, "CA") is True
    assert screener_markets.row_matches_market({"country": "Canada"}, "CA") is True
    assert screener_markets.row_matches_market({"symbol": "AAPL"}, "US") is True
    assert screener_markets.row_matches_market({"country_code": "US"}, "CA") is False


def test_new_market_requires_only_registry_metadata_and_feature_flag(monkeypatch, tmp_path):
    uk = screener_markets.ScreenerMarket(
        code="GB",
        slug="gb",
        label="United Kingdom",
        short_label="UK",
        flag_src="/assets/flags/gb.svg",
        row_values=frozenset({"gb", "gbr", "united kingdom"}),
        route_aliases=frozenset({"uk", "united-kingdom"}),
    )
    monkeypatch.setattr(
        screener_markets,
        "MARKET_REGISTRY",
        screener_markets.MARKET_REGISTRY + (uk,),
    )
    _set_enabled_markets(monkeypatch, tmp_path, {"US": True, "CA": True, "GB": True})

    assert [market.code for market in screener_markets.available_screener_markets()] == ["US", "CA", "GB"]
    assert screener_markets.market_from_path("/screener/uk") == uk
    assert screener_markets.market_path("GB") == "/screener/gb"
