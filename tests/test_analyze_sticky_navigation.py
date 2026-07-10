from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_global_topbar_scrolls_with_document():
    styles = (ROOT / "assets/style/_search.scss").read_text()
    topbar = styles.split(".topbar {", 1)[1].split("}", 1)[0]
    assert "position: relative" in topbar
    assert "position: sticky" not in topbar


def test_analyze_section_navigation_is_sticky():
    styles = (ROOT / "assets/style/_portfolio.scss").read_text()
    jump_nav = styles.split(".analysis-jump-nav {", 1)[1].split("}", 1)[0]
    assert "position: sticky" in jump_nav
    assert "top: 0" in jump_nav
