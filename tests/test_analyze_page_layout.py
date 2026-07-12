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


def test_app_footer_stays_at_bottom_and_is_not_white():
    repo_root = Path(__file__).resolve().parents[1]
    app_shell_scss = (repo_root / "assets/style/_app-shell.scss").read_text()
    runtime_css = (repo_root / "assets/zz_runtime_fixes.css").read_text()

    assert "display: flex;" in app_shell_scss
    assert "flex-direction: column;" in app_shell_scss
    assert "min-height: 100vh;" in app_shell_scss
    assert "margin-top: auto;" in app_shell_scss
    assert ".app-container {\n  display: flex;\n  flex-direction: column;" in runtime_css
    assert "padding-bottom: 0 !important;" in runtime_css
    assert ".app-footer {\n  margin-top: auto;" in runtime_css
    assert "background: #161d2a;" in runtime_css
    assert "body.light .app-footer {\n  background: #f7f8fa;" in runtime_css


def test_dark_shell_background_covers_dash_loading_gaps():
    repo_root = Path(__file__).resolve().parents[1]
    runtime_css = (repo_root / "assets/zz_runtime_fixes.css").read_text()
    app_py = (repo_root / "codes/app.py").read_text()

    assert 'const APP_VERSION = "v3.6";' in app_py
    assert "body:has(#tab-screener.block)" in runtime_css
    assert "body:not(.light) #react-entry-point" in runtime_css
    assert "body:not(.light) #_dash-app-content" in runtime_css
    assert "body:not(.light) #screener-table-container" in runtime_css
    assert "body:not(.light) .screener-market-shell" in runtime_css
    assert "body:not(.light) .dash-loading" in runtime_css
    assert "body:not(.light) ._dash-loading" in runtime_css
    assert "background: #0d1117 !important;" in runtime_css
