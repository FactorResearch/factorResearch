"""Shared section-level async state renderer."""

from dash import html

from .primitives import alert, button, empty_state, progress, skeleton, status_region
from .schemas import SectionState, UIState


def analysis_section(
    title: str, content, state: SectionState, *, section_id: str, optional: bool = False
):
    announcement = state.message or state.state.value.replace("_", " ").title()
    if state.state in {UIState.LOADING, UIState.REFRESHING}:
        body = [
            state.stale_content if state.state == UIState.REFRESHING else None,
            progress(state.progress, label=announcement)
            if state.progress is not None
            else skeleton(label=announcement),
        ]
    elif state.state == UIState.EMPTY:
        body = empty_state("No data yet", announcement)
    elif state.state in {UIState.ERROR, UIState.UNAVAILABLE}:
        retry = (
            button("Try again", id=state.retry_id, variant="secondary") if state.retry_id else None
        )
        body = alert(
            [announcement, retry], tone="danger" if state.state == UIState.ERROR else "warning"
        )
    elif state.state in {UIState.PARTIAL, UIState.STALE, UIState.WARNING}:
        body = [alert(announcement, tone="warning"), state.stale_content or content]
    elif state.state == UIState.DISABLED:
        body = alert(announcement, tone="info")
    else:
        body = content
    return html.Section(
        [
            html.H2(title, className="ds-section__title"),
            status_region(announcement, className="sr-only"),
            body,
        ],
        id=section_id,
        className=f"ds-section ds-section--{state.state.value}"
        + (" ds-section--optional" if optional else ""),
        **{"data-ui-state": state.state.value},
    )
