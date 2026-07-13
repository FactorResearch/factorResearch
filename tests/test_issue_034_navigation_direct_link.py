from types import SimpleNamespace
from unittest.mock import patch

from codes.app_modules.tabs import navigation


def test_analyze_path_selects_analyze_tab_even_when_initial_trigger_is_not_url():
    with patch.object(navigation.dash, "ctx", SimpleNamespace(triggered_id="tab-screener-btn")):
        result = navigation.switch_tabs(
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "/analyze/AAPL/20260711",
        )

    assert result[0] == {"display": "none"}
    assert result[1] == {"display": "block"}
    assert result[5] == "topbar-nav-btn tab-btn"
    assert result[6] == "topbar-nav-btn tab-btn active"


def test_explicit_tab_click_can_leave_analyze_path():
    with patch.object(navigation.dash, "ctx", SimpleNamespace(triggered_id="tab-portfolio-btn")):
        result = navigation.switch_tabs(
            None,
            None,
            1,
            None,
            None,
            None,
            None,
            "/analyze/AAPL/20260711",
        )

    assert result[0] == {"display": "none"}
    assert result[1] == {"display": "none"}
    assert result[2] == {"display": "block"}
    assert result[7] == "topbar-nav-btn tab-btn active"


def test_explicit_screener_click_can_leave_analyze_path():
    with patch.object(navigation.dash, "ctx", SimpleNamespace(triggered_id="tab-screener-btn")):
        result = navigation.switch_tabs(
            1,
            None,
            None,
            None,
            None,
            None,
            None,
            "/analyze/AAPL/20260711",
        )

    assert result[0] == {"display": "block"}
    assert result[1] == {"display": "none"}
    assert result[5] == "topbar-nav-btn tab-btn active"


def test_unrelated_rerun_preserves_latest_portfolio_tab_click():
    with patch.object(navigation.dash, "ctx", SimpleNamespace(triggered_id="url")):
        result = navigation.switch_tabs(
            1,
            None,
            1,
            None,
            None,
            None,
            None,
            "/",
            100,
            None,
            500,
            None,
            None,
        )

    assert result[0] == {"display": "none"}
    assert result[2] == {"display": "block"}
    assert result[5] == "topbar-nav-btn tab-btn"
    assert result[7] == "topbar-nav-btn tab-btn active"
