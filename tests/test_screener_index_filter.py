from types import SimpleNamespace
from unittest.mock import Mock

from codes.app_modules.tabs import screener as screener_tab
from codes.app_modules import layout
from codes.data.us_indices import US_INDEX_OPTIONS, row_matches_any_index, row_matches_index


def _row(symbol, sector="Technology"):
    return {
        "symbol": symbol,
        "name": f"{symbol} Inc.",
        "sector": sector,
        "market_cap": 1000,
        "composite_score": 72,
        "graham_number": None,
        "buffett_iv": None,
        "updated_at": "2026-07-10",
        "verdict": "HIGH CONVICTION",
        "verdict_label": "high-conviction",
        "analyzed": True,
        "price": 170,
    }


def test_us_index_options_include_major_index_filters():
    values = {option["value"] for option in US_INDEX_OPTIONS}

    assert values == {"", "sp500", "sp100", "nasdaq100", "dow30"}


def test_row_matches_index_filters_membership():
    assert row_matches_index({"symbol": "AAPL"}, "sp500") is True
    assert row_matches_index({"symbol": "XYZ_NOT_REAL"}, "sp500") is False
    assert row_matches_index({"symbol": "XYZ_NOT_REAL"}, "") is True


def test_row_matches_any_index_filters_multiple_memberships():
    assert row_matches_any_index({"symbol": "AAPL"}, ["sp500", "dow30"]) is True
    assert row_matches_any_index({"symbol": "MELI"}, ["nasdaq100", "dow30"]) is True
    assert row_matches_any_index({"symbol": "XYZ_NOT_REAL"}, ["sp500", "dow30"]) is False
    assert row_matches_any_index({"symbol": "XYZ_NOT_REAL"}, ["sp500_vix"]) is True
    assert row_matches_any_index({"symbol": "XYZ_NOT_REAL"}, ["sp500_vix", "sp500"]) is False
    assert row_matches_any_index({"symbol": "XYZ_NOT_REAL"}, []) is True


def test_update_index_filter_allows_max_two_indices(monkeypatch):
    monkeypatch.setattr(screener_tab.dash, "ctx", SimpleNamespace(triggered_id={"type": "index-filter-pill", "index": "dow30"}))
    assert screener_tab.update_index_filter([1], ["sp500", "nasdaq100"]) is screener_tab.dash.no_update

    monkeypatch.setattr(screener_tab.dash, "ctx", SimpleNamespace(triggered_id={"type": "index-filter-pill", "index": "sp500"}))
    assert screener_tab.update_index_filter([1], ["sp500", "nasdaq100"]) == ["nasdaq100"]

    monkeypatch.setattr(screener_tab.dash, "ctx", SimpleNamespace(triggered_id={"type": "index-filter-pill", "index": "dow30"}))
    assert screener_tab.update_index_filter([1], ["sp500"]) == ["sp500", "dow30"]


def test_screener_country_tabs_are_non_submit_buttons(monkeypatch):
    countries = [
        {"code": "US", "label": "United States", "short_label": "U.S.", "flag_src": "/assets/flags/us.svg"},
        {"code": "CA", "label": "Canada", "short_label": "Canada", "flag_src": "/assets/flags/ca.svg"},
    ]
    monkeypatch.setattr(screener_tab, "available_screener_countries", lambda: countries)
    monkeypatch.setattr(layout, "available_screener_countries", lambda: countries)

    rendered_buttons = screener_tab._country_tab_buttons("CA")
    initial_buttons = layout._screener_country_tabs("US")

    assert [button.type for button in rendered_buttons] == ["button", "button"]
    assert [button.type for button in initial_buttons] == ["button", "button"]
    assert "active" in rendered_buttons[1].className
    assert "active" in initial_buttons[0].className


def test_render_screener_table_filters_by_index(monkeypatch):
    screener_tab.last_screener_state = None
    monkeypatch.setattr(screener_tab.dash, "ctx", SimpleNamespace(triggered_id="index-filter"))
    monkeypatch.setattr(screener_tab, "get_user_id", lambda: "u1")
    monkeypatch.setattr(screener_tab, "get_portfolio_symbols", lambda: {})
    monkeypatch.setattr(
        screener_tab.screener,
        "get_progress",
        lambda: {"running": False, "total": 2, "done": 2},
    )
    monkeypatch.setattr(
        screener_tab.screener,
        "get_screener_results",
        lambda: [_row("AAPL"), _row("XYZ_NOT_REAL", "Financials")],
    )
    tracked = Mock()
    monkeypatch.setattr(screener_tab.product_analytics, "track_event", tracked)

    table_container, sector_options, page_reset = screener_tab.render_screener_table(
        -1,
        "US",
        1,
        ["sp500"],
        "",
        {"col": "composite_score", "asc": False},
        1,
        [],
    )

    tbody = table_container.children[0].children[1]
    assert len(tbody.children) == 1
    assert "AAPL" in str(tbody.children[0])
    assert page_reset == 1
    assert sector_options == [
        {"label": "All Sectors", "value": ""},
        {"label": "Technology", "value": "Technology"},
    ]
    tracked.assert_called_once()
    assert tracked.call_args.args[2]["indices"] == ["sp500"]


def test_canada_screener_empty_state_does_not_wait_on_us_progress(monkeypatch):
    screener_tab.last_screener_state = None
    monkeypatch.setattr(screener_tab.dash, "ctx", SimpleNamespace(triggered_id="screener-country-store"))
    monkeypatch.setattr(screener_tab, "get_user_id", lambda: "u1")
    monkeypatch.setattr(screener_tab, "get_portfolio_symbols", lambda: {})
    monkeypatch.setattr(
        screener_tab.screener,
        "get_progress",
        lambda: {"running": True, "total": 100, "done": 10, "current": "AAPL"},
    )
    monkeypatch.setattr(
        screener_tab.screener,
        "get_screener_results",
        lambda: [_row("AAPL")],
    )
    monkeypatch.setattr(screener_tab.product_analytics, "track_event", Mock())

    table_container, _sector_options, _page_reset = screener_tab.render_screener_table(
        0,
        "CA",
        1,
        [],
        "",
        {"col": "composite_score", "asc": False},
        1,
        [],
    )

    assert "No Canada screener data loaded yet" in str(table_container)
    assert "Loading in background" not in str(table_container)
