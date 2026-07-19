from pathlib import Path

from codes.app_modules.layout import build_layout


ROOT = Path(__file__).resolve().parents[1]


def _tab(tab_id):
    def find(node):
        if getattr(node, "id", None) == tab_id:
            return node
        children = getattr(node, "children", None)
        if children is None:
            return None
        if not isinstance(children, (list, tuple)):
            children = [children]
        for child in children:
            found = find(child)
            if found is not None:
                return found
        return None

    return find(build_layout())


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


def test_compiled_styles_include_shell_and_analysis_navigation():
    css = (ROOT / "assets/style.css").read_text()
    for selector in (".app-container", ".app-footer", ".analysis-jump-nav"):
        assert selector in css
