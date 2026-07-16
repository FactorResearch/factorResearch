import json
from pathlib import Path

import pytest

from codes.app_modules.design_system.catalogue import build_catalogue
from codes.app_modules.design_system.primitives import (
    alert,
    button,
    confirmation_dialog,
    input_control,
    retry_panel,
    skeleton,
    tooltip,
)
from codes.app_modules.design_system.schemas import InteractionState
from codes.app_modules.design_system.tokens import LIGHT_OVERRIDES, token_map
from codes.app_modules.layout import build_layout

ROOT = Path(__file__).resolve().parents[1]


def _json(component) -> str:
    return json.dumps(
        component.to_plotly_json(),
        default=lambda value: value.to_plotly_json(),
        sort_keys=True,
    )


def _luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("state", list(InteractionState))
def test_button_documents_every_interaction_state(state):
    rendered = button("Action", state=state, id=f"state-{state.value}")
    payload = _json(rendered)
    assert f'"data-state": "{state.value}"' in payload
    assert f"is-{state.value}" in rendered.className
    if state in {InteractionState.DISABLED, InteractionState.LOADING}:
        assert rendered.disabled is True
    if state == InteractionState.SELECTED:
        toggle = button("Toggle", state=state, selected=True)
        assert toggle.to_plotly_json()["props"]["aria-pressed"] == "true"
    if state == InteractionState.READ_ONLY:
        assert rendered.disabled is True


def test_form_alert_loading_and_tooltip_semantics_are_centralized():
    readonly = input_control(control_id="readonly", value="BRK.B", state="read-only")
    assert readonly.readOnly is True
    assert "is-read-only" in readonly.className
    assert alert("Caution", tone="warning").role == "status"
    assert alert("Immediate failure", tone="danger", urgent=True).role == "alert"
    assert skeleton().to_plotly_json()["props"]["aria-hidden"] == "true"
    tip = tooltip("Supplementary detail", button("Explain"), tooltip_id="tip")
    payload = _json(tip)
    assert '"tabIndex": 0' in payload
    assert '"aria-describedby": "tip"' in payload
    assert '"role": "tooltip"' in payload
    assert "Try again" in _json(retry_panel("Provider unavailable", retry_id="retry"))


def test_confirmation_dialog_owns_overlay_and_destructive_contract():
    dialog = confirmation_dialog(
        "Delete account?",
        "This cannot be undone.",
        modal_id="confirm-delete",
        confirm_id="confirm",
        cancel_id="cancel",
        open=True,
    )
    payload = _json(dialog)
    assert '"aria-modal": "true"' in payload
    assert '"data-ds-overlay": "modal"' in payload
    assert '"data-ds-close": "true"' in payload
    assert "ds-button--danger" in payload
    adapter = (ROOT / "assets/design_system.js").read_text()
    for contract in ("Escape", "focusableSelector", "ds-overlay-lock", "previousFocus"):
        assert contract in adapter


def test_dark_and_light_semantic_pairs_exceed_normal_text_contrast():
    dark = token_map()
    assert _contrast(dark["color-text-primary"], dark["color-surface-canvas"]) >= 4.5
    assert _contrast(dark["color-text-muted"], dark["color-surface-canvas"]) >= 4.5
    assert _contrast(dark["color-surface-canvas"], dark["color-action-primary"]) >= 4.5
    assert (
        _contrast(LIGHT_OVERRIDES["color-text-primary"], LIGHT_OVERRIDES["color-surface-canvas"])
        >= 4.5
    )
    assert (
        _contrast(LIGHT_OVERRIDES["color-text-muted"], LIGHT_OVERRIDES["color-surface-canvas"])
        >= 4.5
    )
    assert (
        _contrast(LIGHT_OVERRIDES["color-surface-canvas"], LIGHT_OVERRIDES["color-action-primary"])
        >= 4.5
    )


def test_major_screen_controls_use_shared_production_primitives():
    banned = (
        "html.Button(",
        "html.Table(",
        "dcc.Link(",
        "dcc.Loading(",
        "dcc.Input(",
        "dcc.Dropdown(",
        "dcc.Slider(",
        "dcc.Checklist(",
        "dcc.RadioItems(",
    )
    app_modules = ROOT / "codes/app_modules"
    for source in app_modules.rglob("*.py"):
        if "design_system" in source.parts:
            continue
        contents = source.read_text()
        for constructor in banned:
            assert constructor not in contents, f"{source}: bypasses {constructor}"

    payload = _json(build_layout())
    for shared_class in ("ds-button", "ds-link", "ds-input", "ds-select"):
        assert shared_class in payload


def test_catalogue_covers_financial_text_mobile_and_critical_components():
    payload = _json(build_catalogue(theme="light", viewport="mobile"))
    for example in (
        "Berkshire Hathaway Class B",
        "CAD market value",
        "Unavailable estimate",
        "Not applicable for this security type",
        "Delete account",
        "Degraded data",
        "Indeterminate catalogue progress",
    ):
        assert example in payload
    for state in InteractionState:
        assert f'"data-state": "{state.value}"' in payload


def test_visual_regression_and_review_policy_are_release_gated():
    audit = (ROOT / "scripts/audit-design-system.mjs").read_text()
    for context in ("light", "dark", "mobile", "desktop", "axe.run", "differenceRatio"):
        assert context in audit
    for image in (
        "light-mobile.png",
        "dark-mobile.png",
        "light-desktop.png",
        "dark-desktop.png",
    ):
        assert (ROOT / "artifacts/design-system/visuals" / image).exists()
    checklist = (ROOT / "docs/design-system-review-checklist.md").read_text().lower()
    assert "one-off component" in checklist
    assert "focus trap" in checklist
    assert "financial meaning" in checklist
    gate = (ROOT / "scripts/release-gate.sh").read_text()
    assert "check-design-system.py" in gate
    assert "assets/design_system.js" in gate
