import json
from pathlib import Path

import pytest
from dash import dcc, html

from codes.app_modules.analysis_ui import _build_analysis_content
from codes.app_modules.tabs import portfolio
from codes.app_modules.design_system.catalogue import catalogue_matrix
from codes.app_modules.design_system.financial import (
    data_freshness,
    delta,
    format_financial,
    score_badge,
)
from codes.app_modules.design_system.primitives import button, form_field
from codes.app_modules.design_system.schemas import (
    SectionDefinition,
    SectionRegistry,
    SectionState,
    UIState,
)
from codes.app_modules.design_system.states import analysis_section
from codes.app_modules.design_system.tokens import TOKEN_GROUPS, css_variable, token_map

ROOT = Path(__file__).resolve().parents[1]


def _json(component) -> str:
    return json.dumps(
        component.to_plotly_json(),
        default=lambda value: value.to_plotly_json(),
        sort_keys=True,
    )


def test_typed_tokens_cover_every_required_category_and_generated_css():
    groups = {group.name for group in TOKEN_GROUPS}
    assert groups == {
        "color",
        "font",
        "text",
        "space",
        "border",
        "radius",
        "shadow",
        "layer",
        "breakpoint",
        "container",
        "motion",
        "density",
        "target",
        "chart",
        "table",
    }
    assert css_variable("color-surface-raised") == "var(--fr-color-surface-raised)"
    generated = (ROOT / "assets/style/_design_tokens.generated.scss").read_text()
    for name, value in token_map().items():
        assert f"--fr-{name}: {value};" in generated
    assert "[data-theme='light']" in generated
    assert "[data-theme='dark']" in generated


def test_financial_formatting_and_direction_never_require_color_alone():
    assert format_financial(1250000000, "compact") == "1.2B"
    assert format_financial(12.345, "percent", decimals=2) == "12.35%"
    assert format_financial(None, "currency") == "Not available"
    assert "\\u25bc" in _json(delta(-3.2))
    assert "Weak" in _json(score_badge(20))
    assert "Freshness unavailable" in _json(data_freshness(None))


def test_interactive_primitives_own_keyboard_and_state_semantics():
    loading = button("Save", loading=True, id="save")
    assert loading.disabled is True
    assert '"aria-busy": "true"' in _json(loading)
    field = form_field("Ticker", dcc.Input(id="ticker"), error="Required")
    assert field.children[0].htmlFor == "ticker"
    assert field.children[-1].role == "alert"
    css = (ROOT / "assets/style/_design_system.scss").read_text()
    assert ":focus-visible" in css
    assert "--fr-target-minimum" in css
    assert "prefers-reduced-motion" in css
    assert "prefers-contrast" in css


@pytest.mark.parametrize("state", list(UIState))
def test_common_async_contract_renders_every_state_with_announcements(state):
    rendered = analysis_section(
        "Valuation",
        html.Div("Content"),
        SectionState(
            state,
            f"{state.value} message",
            progress=50 if state in {UIState.LOADING, UIState.REFRESHING} else None,
            retry_id="retry" if state == UIState.ERROR else None,
            stale_content=html.Div("Cached")
            if state in {UIState.PARTIAL, UIState.REFRESHING, UIState.STALE}
            else None,
        ),
        section_id=f"state-{state.value}",
    )
    payload = _json(rendered)
    assert f'"data-ui-state": "{state.value}"' in payload
    assert '"aria-live": "polite"' in payload
    if state == UIState.ERROR:
        assert "Try again" in payload


def test_schema_validates_order_uniqueness_and_ui_only_rendering():
    definitions = [
        SectionDefinition("second", "metric", 20, "b", analytics_id="second"),
        SectionDefinition("first", "metric", 10, "a", analytics_id="first"),
    ]
    registry = SectionRegistry({"metric": lambda value: f"rendered:{value}"})
    assert registry.render(definitions, {"a": 1, "b": 2}) == ["rendered:1", "rendered:2"]
    with pytest.raises(ValueError, match="duplicate"):
        registry.render([definitions[0], definitions[0]], {})
    with pytest.raises(ValueError, match="responsive_span"):
        SectionDefinition("bad", "metric", 1, "a", responsive_span=13)


def test_catalogue_covers_themes_breakpoints_long_text_and_all_states():
    matrix = catalogue_matrix()
    assert len(matrix) == 4
    payload = "\n".join(_json(item) for item in matrix)
    for theme in ("light", "dark"):
        assert f'"data-theme": "{theme}"' in payload
    for viewport in ("mobile", "desktop"):
        assert f'"data-viewport": "{viewport}"' in payload
    for state in UIState:
        assert f'"data-ui-state": "{state.value}"' in payload
    assert "localized values" in payload


def test_analyze_reference_uses_typed_schema_and_shared_layout():
    data = {
        "symbol": "NULL",
        "name": "Nullable Corp",
        "sector": "Unknown",
        "price": None,
        "graham": {"criteria": [], "pe": None, "pb": None, "eps_history": []},
        "quality": {"criteria": [], "roe": None, "op_margin": None},
        "momentum": {"criteria": []},
        "enhanced": {"composite_score": 50, "verdict": "WATCH", "verdict_label": "watch"},
        "risk": {"beta": None, "sharpe": None},
    }
    rendered = str(_build_analysis_content(data))
    assert "analysis-design-engine-reference" in rendered
    assert "data-design-system='issue-075'" in rendered
    assert "data-analytics-id='analysis_overview'" in rendered


def test_portfolio_reference_uses_financial_layout_and_table_primitives(monkeypatch):
    monkeypatch.setattr(portfolio, "get_user_id", lambda: "user")
    monkeypatch.setattr(
        portfolio.portfolio_engine,
        "load_portfolio",
        lambda *_: {
            "holdings": {
                "ABC": {
                    "shares": 10,
                    "price_at_add": 100,
                    "current_price": 95,
                    "company": "ABC Corp",
                }
            }
        },
    )
    monkeypatch.setattr(
        portfolio.db,
        "get_analysis_entries",
        lambda *_: {"ABC": {"data": {"composite_score": 72, "risk": {"sharpe": 1.1}}}},
    )
    rendered = str(portfolio.render_portfolio_holdings("Core", 0))
    assert "portfolio-design-engine-reference" in rendered
    assert "ds-table portfolio-table" in rendered
    assert "▼" in rendered
    assert "Return -5.0%" in rendered
    assert "ds-mobile-actions" in rendered


def test_enforcement_and_documentation_are_release_gated():
    gate = (ROOT / "scripts/release-gate.sh").read_text()
    assert "generate-design-tokens.py" in gate
    assert "check-design-system.py" in gate
    documentation = (ROOT / "docs/design-system.md").read_text()
    for topic in (
        "add a token",
        "Add a variant",
        "Add a formatter",
        "SectionDefinition",
        "Analyze",
        "Portfolio",
    ):
        assert topic.lower() in documentation.lower()
