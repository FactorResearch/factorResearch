"""Factor Research design engine public API."""

from .financial import (
    data_freshness,
    delta,
    format_financial,
    metric_value,
    model_verdict,
    score_badge,
)
from .layouts import analysis_grid, container, dashboard_grid, page_header, stack
from .primitives import alert, button, card, empty_state, form_field, status_region
from .schemas import SectionDefinition, SectionRegistry, SectionState, UIState

__all__ = [
    "SectionDefinition",
    "SectionRegistry",
    "SectionState",
    "UIState",
    "alert",
    "analysis_grid",
    "button",
    "card",
    "container",
    "dashboard_grid",
    "data_freshness",
    "delta",
    "empty_state",
    "form_field",
    "format_financial",
    "metric_value",
    "model_verdict",
    "page_header",
    "score_badge",
    "stack",
    "status_region",
]
