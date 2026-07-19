"""Regression coverage for the Factor Lab top-level navigation tab."""

from unittest.mock import patch
from types import SimpleNamespace

from codes.app_modules import layout
from codes.app_modules.tabs import navigation


def _find_by_id(component, target_id):
    if getattr(component, "id", None) == target_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        found = _find_by_id(child, target_id)
        if found is not None:
            return found
    return None


def test_rail_exposes_factor_lab_beside_portfolio():
    rail = layout._rail()
    nav = _find_by_id(rail, "tab-factorlab-btn")
    portfolio = _find_by_id(rail, "tab-portfolio-btn")
    profile_button = _find_by_id(rail, "profile-menu-btn")

    assert nav.children == "Factor Lab"
    assert rail.children[2].children.index(nav) == rail.children[2].children.index(portfolio) + 1
    assert profile_button is not None


def test_factor_lab_button_shows_page_and_sets_active_state():
    with patch.object(navigation.dash, "ctx", SimpleNamespace(triggered_id="tab-factorlab-btn")):
        result = navigation.switch_tabs(0, 0, 0, 1, 0, None, None, "/")

    assert result[:6] == (
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        {"display": "block"},
        {"display": "none"},
        {"display": "none"},
    )
    assert result[6:] == (
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn active",
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn",
    )


def test_background_job_cancel_controls_are_present_in_initial_layout():
    """Keep async cancel inputs in the initial layout for Dash callback validation."""
    root = layout.build_layout()
    assert _find_by_id(root, "factor-job-cancel") is not None
    assert _find_by_id(root, "portfolio-job-cancel") is not None
