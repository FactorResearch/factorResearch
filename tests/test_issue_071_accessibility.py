from pathlib import Path

from dash import html

from codes.app_modules.design_system.financial import (
    FinancialFormat,
    delta,
    format_financial_spoken,
    metric_value,
)
from codes.app_modules.design_system.primitives import form_field, input_control, table
from codes.app_modules.layout import build_layout


ROOT = Path(__file__).resolve().parents[1]


def test_application_has_skip_navigation_tab_semantics_and_live_statuses():
    rendered = str(build_layout())
    assert "Skip to main content" in rendered
    assert "role='tablist'" in rendered
    assert rendered.count("role='tabpanel'") == 5
    assert "aria-controls='tab-screener'" in rendered
    assert rendered.count("aria-live='polite'") >= 10


def test_financial_values_have_unambiguous_spoken_equivalents():
    assert format_financial_spoken(-1250.5, FinancialFormat.CURRENCY) == "negative 1,250.5 US dollars"
    assert format_financial_spoken(-8.2, FinancialFormat.PERCENT) == "negative 8.2 percent"
    assert format_financial_spoken(None) == "Not available"
    rendered = str(metric_value("Portfolio value", -1250.5, kind=FinancialFormat.CURRENCY))
    assert "Portfolio value: negative 1,250.5 US dollars" in rendered
    assert "aria-hidden='true'" in rendered
    assert "negative 4.5 percent" in str(delta(-4.5, label="Return"))


def test_shared_forms_and_tables_expose_error_caption_and_header_contracts():
    field = str(form_field("Email", input_control(id="email"), error="Enter a valid email", required=True))
    assert "id='email-message'" in field
    assert "data-required='true'" in field
    assert "role='alert'" in field

    rendered = str(
        table(
            [html.Thead(html.Tr([html.Th("Ticker"), html.Th("Score")])), html.Tbody()],
            caption="Stock scores",
        )
    )
    assert "Stock scores" in rendered
    assert rendered.count("scope='col'") == 2


def test_browser_layer_supports_keyboard_focus_restoration_and_chart_equivalents():
    javascript = (ROOT / "assets" / "design_system.js").read_text()
    for contract in (
        "ArrowLeft",
        "ArrowRight",
        "dsCloseController",
        "previousFocus",
        "ds-chart-data",
        "aria-describedby",
        "aria-sort",
    ):
        assert contract in javascript or contract in (ROOT / "codes/app_modules/tabs/screener.py").read_text()


def test_ci_audit_covers_all_critical_application_surfaces():
    audit = (ROOT / "scripts" / "audit-accessibility.mjs").read_text()
    workflow = (ROOT / ".github/workflows/pr-tests.yml").read_text()
    for surface in (
        "screener",
        "analyze",
        "portfolio",
        "factor-lab",
        "pricing",
        "landing",
        "terms",
        "privacy",
        "error-state",
    ):
        assert surface in audit
    assert "Run critical-journey WCAG 2.2 AA audit" in workflow
    assert "npm run audit:a11y" in workflow


def test_standalone_pages_expose_skip_links_and_status_semantics():
    landing = (ROOT / "codes/templates/landing.html").read_text()
    privacy = (ROOT / "codes/templates/privacy.html").read_text()
    error = (ROOT / "codes/templates/errors/500.html").read_text()
    assert 'class="skip-link"' in landing
    assert 'id="main-content"' in landing
    assert 'role="status"' in landing
    assert 'aria-live="polite"' in privacy
    assert 'class="skip-link"' in error
