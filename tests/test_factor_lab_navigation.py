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


def test_topbar_exposes_factor_lab_beside_portfolio():
    topbar = layout._topbar()
    nav = _find_by_id(topbar, "tab-factorlab-btn")
    portfolio = _find_by_id(topbar, "tab-portfolio-btn")

    assert nav.children == "Factor Lab"
    assert topbar.children[1].children.index(nav) == topbar.children[1].children.index(portfolio) + 1


def test_factor_lab_button_shows_page_and_sets_active_state():
    with patch.object(navigation.dash, "ctx", SimpleNamespace(triggered_id="tab-factorlab-btn")):
        result = navigation.switch_tabs(0, 0, 0, 1, None, "/")

    assert result[:4] == (
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        {"display": "block"},
    )
    assert result[4:] == (
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn active",
    )
