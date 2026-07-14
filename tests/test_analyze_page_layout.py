from pathlib import Path

from codes.app_modules.layout import build_layout


ROOT = Path(__file__).resolve().parents[1]


def _tab(tab_id):
    return next(child for child in build_layout().children if getattr(child, "id", None) == tab_id)


def test_add_to_portfolio_panel_is_after_analysis_content():
    ids = [getattr(child, "id", None) for child in _tab("tab-analyze").children]
    assert ids.index("analysis-loading") < ids.index("add-to-portfolio-panel")
    assert ids.index("add-to-portfolio-panel") < ids.index("analysis-anchor-scroll-trigger")


def test_screener_toolbar_does_not_include_manual_universe_loader():
    def collect_ids(node):
        children = getattr(node, "children", None)
        ids = [node.id] if getattr(node, "id", None) else []
        if isinstance(children, (list, tuple)):
            for child in children:
                ids.extend(collect_ids(child))
        elif children is not None:
            ids.extend(collect_ids(children))
        return ids

    assert "load-universe-btn" not in collect_ids(_tab("tab-screener"))


def test_shell_and_analysis_layout_are_owned_by_scss_components():
    shell = (ROOT / "assets/style/_app-shell.scss").read_text()
    tabs = (ROOT / "assets/style/_tabs.scss").read_text()
    assert ".app-container" in shell
    assert "min-height: 100vh" in shell
    assert ".app-footer" in shell
    assert ".analysis-jump-nav" in tabs
