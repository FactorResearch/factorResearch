from pathlib import Path

from codes.app_modules.layout import build_layout


def test_add_to_portfolio_panel_is_after_analysis_content():
    layout = build_layout()
    tab_analyze = next(child for child in layout.children if getattr(child, "id", None) == "tab-analyze")
    child_ids = [getattr(child, "id", None) for child in tab_analyze.children]

    assert child_ids.index("analysis-loading") < child_ids.index("add-to-portfolio-panel")
    assert child_ids.index("add-to-portfolio-panel") < child_ids.index("analysis-anchor-scroll-trigger")


def test_screener_toolbar_does_not_include_load_universe_button():
    layout = build_layout()
    tab_screener = next(child for child in layout.children if getattr(child, "id", None) == "tab-screener")

    def _collect_ids(node):
        ids = []
        children = getattr(node, "children", None)
        if getattr(node, "id", None):
            ids.append(getattr(node, "id"))
        if isinstance(children, (list, tuple)):
            for child in children:
                ids.extend(_collect_ids(child))
        elif children is not None:
            ids.extend(_collect_ids(children))
        return ids

    assert "load-universe-btn" not in _collect_ids(tab_screener)


def test_add_to_portfolio_panel_uses_horizontal_runtime_styles():
    css = (Path(__file__).resolve().parents[1] / "assets/zz_runtime_fixes.css").read_text()

    assert "#sector-filter .Select-control" in css
    assert "body.light #sector-filter .Select-control" in css
    assert "#tab-analyze .analyze-ticker-input input" in css
    assert "min-width: 220px" in css
    assert "width: min(100%, 360px)" in css
    assert "#add-to-portfolio-panel .portfolio-add-panel" in css
    assert "flex-direction: row" in css
    assert "#add-to-portfolio-panel .portfolio-add-controls" in css
