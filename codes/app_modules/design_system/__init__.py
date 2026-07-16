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
from .states import (
    background_job_status,
    card_skeleton,
    chart_skeleton,
    inline_pending_indicator,
    partial_data_notice,
    section_error,
    stage_progress,
    stale_data_notice,
    table_skeleton,
)

__all__ = [
    "SectionDefinition",
    "SectionRegistry",
    "SectionState",
    "UIState",
    "alert",
    "analysis_grid",
    "background_job_status",
    "button",
    "card_skeleton",
    "chart_skeleton",
    "card",
    "container",
    "dashboard_grid",
    "data_freshness",
    "delta",
    "empty_state",
    "form_field",
    "format_financial",
    "inline_pending_indicator",
    "metric_value",
    "model_verdict",
    "page_header",
    "partial_data_notice",
    "score_badge",
    "section_error",
    "stack",
    "stage_progress",
    "stale_data_notice",
    "status_region",
    "table_skeleton",
]
