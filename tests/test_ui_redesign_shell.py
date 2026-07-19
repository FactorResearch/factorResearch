"""Regression checks for the small, production-safe shell migration slices."""

from pathlib import Path

from codes.app_modules.layout import _rail, _topbar, _bottom_nav, build_layout
from codes.app_modules.tabs.screener import SCREENER_DEFAULT_COLUMNS


ROOT = Path(__file__).resolve().parents[1]


def test_topbar_uses_an_existing_cenvarn_logo_asset():
    """The shell must not request the removed legacy logo.svg asset."""
    image = next(child for child in _topbar().children[0].children if getattr(child, "src", None))
    assert image.src == "/assets/logo-icon.svg"
    assert (ROOT / "assets/logo-icon.svg").exists()


def test_mockup_shell_has_real_rail_workspace_and_mobile_nav():
    """The shell must use semantic containers instead of pseudo-element rails."""
    shell_styles = (ROOT / "assets/style/_mockup-shell.scss").read_text()
    assert ".rail" in shell_styles and ".workspace" in shell_styles and ".bottom-nav" in shell_styles
    assert getattr(_rail(), "className", "") == "rail"
    assert getattr(_bottom_nav(), "className", "") == "bottom-nav"


def test_screener_long_text_has_non_overlapping_column_contract():
    """Long company and sector values must truncate within table cells."""
    styles = (ROOT / "assets/style/_screener.scss").read_text()
    assert ".company-name-cell" in styles
    assert "text-overflow: ellipsis" in styles
    assert "white-space: nowrap" in styles
    assert "overflow-x: auto" in styles
    assert ".sort-header-btn" in styles and "min-height: 0" in styles
    shell_styles = (ROOT / "assets/style/_mockup-shell.scss").read_text()
    assert ".screener-table .sort-header-btn" in shell_styles
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in shell_styles
    assert "position: fixed" not in shell_styles[shell_styles.find(".quick-peek-shell"):shell_styles.find(".quick-peek-shell") + 900]


def test_screener_identity_replaces_standalone_columns():
    assert SCREENER_DEFAULT_COLUMNS[0] == "company"
    assert "ticker" not in SCREENER_DEFAULT_COLUMNS
    assert "sector" not in SCREENER_DEFAULT_COLUMNS


def test_screener_progress_callback_has_a_layout_target():
    ids = []

    def collect(node):
        if getattr(node, "id", None):
            ids.append(node.id)
        children = getattr(node, "children", None)
        if children is None:
            return
        if not isinstance(children, (list, tuple)):
            children = [children]
        for child in children:
            collect(child)

    collect(build_layout())
    assert "screener-progress-info" in ids


def test_removed_screener_toolbar_keeps_hidden_callback_state_targets():
    rendered = str(build_layout())
    for target in ("index-filter", "sector-filter", "index-filter-pill-container"):
        assert target in rendered


def test_issue_078_search_is_scoped_to_mockup_rail():
    root = build_layout()
    serialized = str(root)
    assert "sidebar-analyze" in serialized
    assert "global-analyze-search" not in serialized
    assert serialized.count("id='ticker-input'") == 1
    assert serialized.count("id='analyze-btn'") == 1


def test_mockup_rail_autocomplete_uses_compact_surface_styles():
    styles = (ROOT / "assets/style/_mockup-shell.scss").read_text()
    assert ".ticker-suggestions" in styles
    assert "rgba(177, 138, 84, 0.16)" in styles
    assert "grid-template-columns: 52px minmax(0, 1fr)" in styles
