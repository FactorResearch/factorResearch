from pathlib import Path

import pytest
from dash import html

from codes.app_modules import layout
from codes.app_modules.design_system.primitives import responsive_table
from codes.app_modules.tabs import factor_lab, screener
from codes.engine import scorer


ROOT = Path(__file__).resolve().parents[1]


def test_screener_layout_exposes_mobile_filters_columns_density_and_state():
    rendered = str(layout.build_layout())
    for component_id in (
        "screener-filter-summary",
        "screener-clear-all-btn",
        "screener-visible-columns",
        "screener-table-density",
        "screener-scroll-pos",
        "screener-url-state-sink",
    ):
        assert component_id in rendered


def test_screener_query_state_round_trips_safe_values():
    state = screener._screener_state_from_search(
        "?index=sp500&index=nasdaq100&sector=Technology&page=3&sort=market_cap&dir=asc"
    )
    assert state == {
        "indexes": ["sp500", "nasdaq100"],
        "sector": "Technology",
        "page": 3,
        "sort": {"col": "market_cap", "asc": True},
    }

    invalid = screener._screener_state_from_search(
        "?index=invalid&page=oops&sort=__private&dir=asc"
    )
    assert invalid["indexes"] == []
    assert invalid["page"] == 1
    assert invalid["sort"] == {"col": "composite_score", "asc": True}


def test_responsive_table_has_scroll_cue_density_and_sticky_identifier():
    component = responsive_table(
        [html.Thead(html.Tr(html.Th("Ticker"))), html.Tbody()],
        label="Holdings",
        density="compact",
        sticky_identifier=True,
        className="holdings-table",
    )
    assert component.role == "region"
    assert component.tabIndex == 0
    assert component.to_plotly_json()["props"]["data-responsive-table"] == "true"
    assert "has-sticky-identifier" in component.className
    assert "Scroll horizontally" in str(component.children[0])
    assert "holdings-table density-compact" in component.children[1].className

    with pytest.raises(ValueError, match="density"):
        responsive_table([], label="Invalid", density="tiny")


def test_factor_weights_have_one_touch_default_reset():
    values = factor_lab.reset_factor_weights(1)
    assert values == tuple(
        round(scorer.ENHANCED_WEIGHTS.get(key, 0) * 100)
        for key in factor_lab._FB_WEIGHT_KEYS
    )
    assert "fb-reset-weights-btn" in str(layout.build_layout())


def test_responsive_css_and_chart_touch_contracts_are_source_controlled():
    screener_css = (ROOT / "assets/style/_screener.scss").read_text()
    shell_css = (ROOT / "assets/style/_app-shell.scss").read_text()
    design_css = (ROOT / "assets/style/_design_system.scss").read_text()
    browser_js = (ROOT / "assets/design_system.js").read_text()
    audit = (ROOT / "scripts/audit-accessibility.mjs").read_text()

    assert "screener-filter-drawer" in screener_css
    assert "position: sticky" in screener_css
    assert "density-compact" in screener_css
    assert "safe-area-inset-bottom" in shell_css
    assert "touch-action: pan-y pinch-zoom" in design_css
    assert "plotly_click" in browser_js
    assert "responsiveChart" in browser_js
    for profile in ("iphone-sized", "android-sized", "tablet", "laptop", "wide-desktop"):
        assert profile in audit


def test_url_and_scroll_restoration_are_registered_clientside():
    source = (ROOT / "codes/app_modules/tabs/screener.py").read_text()
    assert "history.replaceState" in source
    assert "window.scrollTo(0, saved_pos || 0)" in source
    assert "screener-visible-columns" in source
    assert "screener-table-density" in source
