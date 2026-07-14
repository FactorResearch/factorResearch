from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_light_palette_uses_readable_text_and_status_colors():
    tokens = (ROOT / "assets/style/_tokens.scss").read_text()
    assert "$light-text: #0f172a" in tokens
    assert "$light-text-dim: #475569" in tokens
    assert "$light-text-muted: #64748b" in tokens
    assert "$light-positive: #087f3f" in tokens
    assert "$light-negative: #c62828" in tokens


def test_light_analysis_overrides_dark_inline_tokens_and_component_borders():
    styles = (ROOT / "assets/style/_base.scss").read_text()
    portfolio = (ROOT / "assets/style/_portfolio.scss").read_text()
    assert ".stability-zone" in styles
    assert ".stability-component-row" in styles
    assert 'style*="color: #e8eaf0"' in styles
    assert 'style*="color: #00e676"' in styles
    assert "body.light .risk-row .metric_cell" in portfolio
    assert "border-color: $light-border" in portfolio


def test_issue_038_status_tones_and_dark_labels_are_readable():
    base = (ROOT / "assets/style/_base.scss").read_text()
    scorecards = (ROOT / "assets/style/_scorecards.scss").read_text()
    inline_free = (ROOT / "assets/style/_inline_free.scss").read_text()
    runtime = (ROOT / "assets/zz_runtime_fixes.css").read_text()

    assert ".tone-positive,\n  .clr-green" in base
    assert "color: $light-positive !important;" in base
    assert ".tone-muted" in base
    assert "color: $light-text-dim !important;" in base
    assert ".metric-row-divider,\n  .metric-row-divider--analysis" in base
    assert "border-bottom-color: rgba($light-border, 0.65) !important;" in base
    assert ".criterion-label {\n  @include mono(12px, 500);\n  color: $text-dim;" in scorecards
    assert ".metric-row-divider { border-bottom: 1px solid rgba($text-dim, 0.18); }" in inline_free
    assert "body:not(.light) .analysis-metric-label" in runtime
    assert "color: #8899aa !important;" in runtime
    assert "body.light .tone-positive" in runtime
    assert "color: #087f3f !important;" in runtime
    assert "border-bottom-color: rgba(136, 153, 170, 0.18) !important;" in runtime
    assert "border-bottom-color: rgba(203, 213, 225, 0.65) !important;" in runtime


def test_analyze_company_heading_links_to_company_research():
    source = (ROOT / "codes/app_modules/analysis_ui.py").read_text()
    assert 'href=f"/analyze/{symbol}/"' in source
    assert "refresh=True" in source
    assert 'className="company-title-link"' in source


def test_runtime_css_applies_navigation_scroll_behavior():
    styles = (ROOT / "assets/zz_runtime_fixes.css").read_text()
    assert "#topbar.topbar" in styles
    assert "position: relative !important" in styles
    assert "#tab-analyze .analysis-jump-nav" in styles
    assert "position: sticky !important" in styles
