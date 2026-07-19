"""Regression coverage for portfolio routes, progress, and mockup hierarchy."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import dash
from dash import dcc, html

from codes.app_modules.design_system.primitives import progress
from codes.app_modules.tabs import navigation, portfolio

ROOT = Path(__file__).resolve().parents[1]


def _class_names(component) -> set[str]:
    """Collect class names from a Dash component tree without rendering React."""
    if component is None or isinstance(component, (str, int, float)):
        return set()
    names = set(str(getattr(component, "className", "") or "").split())
    children = getattr(component, "children", None)
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        names.update(_class_names(child))
    return names


def _components_with_class(component, class_name: str) -> list:
    """Return every Dash component carrying one requested CSS class."""
    if component is None or isinstance(component, (str, int, float)):
        return []
    matches = []
    classes = set(str(getattr(component, "className", "") or "").split())
    if class_name in classes:
        matches.append(component)
    children = getattr(component, "children", None)
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        matches.extend(_components_with_class(child, class_name))
    return matches


def test_progress_serializes_dash_html_values_as_strings():
    component = progress(0, label="Starting simulation")

    assert component.value == "0"
    assert component.max == "100"
    assert component.to_plotly_json()["props"]["aria-valuenow"] == "0"


def test_portfolio_name_route_round_trip_uses_url_encoding():
    pathname = portfolio._portfolio_path("Core Portfolio")

    assert pathname == "/portfolio/Core%20Portfolio"
    assert portfolio._portfolio_name_from_path(pathname) == "Core Portfolio"
    assert portfolio._portfolio_name_from_path("/portfolio/%2Fetc") is None


def test_direct_portfolio_route_selects_portfolio_tab():
    with patch.object(navigation.dash, "ctx", SimpleNamespace(triggered_id="url")):
        result = navigation.switch_tabs(0, 0, 0, 0, 0, None, None, "/portfolio/Core%20Portfolio")

    assert result[2] == {"display": "block"}
    assert result[8] == "topbar-nav-btn tab-btn active"


def test_route_selection_is_limited_to_current_users_portfolios():
    with (
        patch.object(portfolio.portfolio_engine, "list_portfolios", return_value=["Core Portfolio"]),
        patch.object(portfolio, "get_user_id", return_value="user-1"),
        patch.object(portfolio.dash, "ctx", SimpleNamespace(triggered_id="url")),
    ):
        options, active_options, compare_options, selected = portfolio.refresh_portfolio_dropdowns(
            0, "/portfolio/Other", None
        )

    assert options == active_options == compare_options
    assert selected is None


def test_portfolio_refresh_does_not_reemit_unchanged_active_selection():
    with (
        patch.object(portfolio.portfolio_engine, "list_portfolios", return_value=["Core"]),
        patch.object(portfolio, "get_user_id", return_value="user-1"),
        patch.object(
            portfolio.dash,
            "ctx",
            SimpleNamespace(triggered_id="portfolio-refresh-store"),
        ),
    ):
        *_, selected = portfolio.refresh_portfolio_dropdowns(1, "/portfolio/Core", "Core")

    assert selected is dash.no_update


def test_same_tab_portfolio_route_updates_do_not_reset_window_scroll():
    source = (ROOT / "codes/app_modules/tabs/screener.py").read_text()

    assert "previousTab === activeTab" in source
    assert "window.__frVisibleResearchTab = activeTab" in source


def test_portfolio_renderer_uses_mockup_dashboard_regions():
    holding = {
        "shares": 10,
        "price_at_add": 100,
        "current_price": 110,
        "company": "Example Inc.",
    }
    analysis = {
        "composite_score": 72,
        "sector": "Technology",
        "updated_at": "2026-07-18T20:00:00+00:00",
        "risk": {"sharpe": 1.2},
    }
    with (
        patch.object(portfolio.portfolio_engine, "load_portfolio", return_value={"holdings": {"EX": holding}}),
        patch.object(
            portfolio.portfolio_engine,
            "analysis_entries",
            return_value={"EX": {"data": analysis, "updated_at": analysis["updated_at"]}},
        ),
        patch.object(portfolio, "get_user_id", return_value="user-1"),
        patch.object(portfolio.product_analytics, "track_event"),
        patch.object(portfolio.performance_metrics, "record_ui_operation"),
    ):
        rendered = portfolio.render_portfolio_holdings("Core", 0)

    assert isinstance(rendered, html.Div)
    classes = _class_names(rendered)
    assert {
        "portfolio-page-heading",
        "portfolio-metric-strip",
        "portfolio-content-grid",
        "portfolio-data-trust",
        "portfolio-allocation-card",
        "portfolio-holdings-card",
        "portfolio-weak-link-card",
    } <= classes
    assert "portfolio-health" not in classes
    assert "portfolio-analysis-card" not in classes

    trust = _components_with_class(rendered, "portfolio-data-trust")[0]
    assert isinstance(trust, html.Details)
    assert not getattr(trust, "open", False)

    allocation = _components_with_class(rendered, "portfolio-allocation-card")[0]
    allocation_graphs = _components_with_class(allocation, "portfolio-allocation-chart")
    assert len(allocation_graphs) == 1
    assert isinstance(allocation_graphs[0], dcc.Graph)
    assert "Technology" in str(allocation)
    assert "100.0%" in str(allocation)

    content_grid = _components_with_class(rendered, "portfolio-content-grid")[0]
    child_classes = [set(child.className.split()) for child in content_grid.children]
    assert "portfolio-allocation-card" in child_classes[0]
    assert "portfolio-weak-link-card" in child_classes[1]
    assert {"portfolio-holdings-card", "portfolio-card-span-3"} <= child_classes[2]
