from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_global_topbar_sticks_with_document():
    styles = (ROOT / "assets/style/_app-shell.scss").read_text()
    app_container = styles.split(".app-container {", 1)[1].split("}", 1)[0]
    topbar = styles.split(".topbar {", 1)[1].split("}", 1)[0]
    assert "overflow-x: clip" in app_container
    assert "overflow-x: hidden" not in app_container
    assert "position: sticky" in topbar
    assert "top: 0" in topbar


def test_analyze_section_navigation_is_sticky():
    styles = (ROOT / "assets/style/_company.scss").read_text()
    jump_nav = styles.split(".analysis-jump-nav {", 1)[1].split("}", 1)[0]
    jump_track = styles.split(".analysis-jump-track {", 1)[1].split("}", 1)[0]
    assert "position: sticky" in jump_nav
    assert "top: 96px" in jump_nav
    assert "overflow" not in jump_nav
    assert "flex-direction: column" in jump_track


def test_analyze_section_navigation_scrolls_inside_sticky_shell():
    styles = (ROOT / "assets/style/_company.scss").read_text()
    tablet_styles = styles.split("@include media.tablet-down", 1)[1]
    jump_track = tablet_styles.split(".analysis-jump-track {", 1)[1].split("}", 1)[0]
    assert "overflow-x: auto" in jump_track
