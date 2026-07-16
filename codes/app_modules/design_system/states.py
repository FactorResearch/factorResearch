"""Shared section-level async state renderer."""

from dash import html

from .primitives import alert, button, empty_state, progress, retry_panel, skeleton, status_region
from .schemas import SectionState, UIState


def card_skeleton(*, label: str = "Loading card"):
    return html.Div(
        skeleton(lines=4, label=label), className="ds-skeleton-frame ds-skeleton-frame--card"
    )


def table_skeleton(*, rows: int = 5, label: str = "Loading table rows"):
    return html.Div(
        [skeleton(lines=1, label=label) for _ in range(max(1, rows))],
        className="ds-skeleton-frame ds-skeleton-frame--table",
        **{"aria-hidden": "true"},
    )


def chart_skeleton(*, label: str = "Loading chart"):
    return html.Div(
        [skeleton(lines=2, label=label), html.P("Chart area reserved")],
        className="ds-skeleton-frame ds-skeleton-frame--chart",
        **{"aria-hidden": "true"},
    )


def stage_progress(stage: str, *, completed: int | None = None, total: int | None = None):
    value = round(completed / total * 100) if completed is not None and total else None
    detail = f"{completed} of {total}" if completed is not None and total else "In progress"
    return html.Div(
        [
            html.Strong(stage),
            html.Span(detail, className="ds-stage__detail"),
            progress(value, label=stage),
        ],
        className="ds-stage",
        **{"aria-busy": "true"},
    )


def background_job_status(snapshot: dict, *, cancel_id=None):
    status = str(snapshot.get("status", "loading"))
    cancel = (
        button("Cancel", id=cancel_id, variant="secondary")
        if cancel_id and status in {"loading", "progress"}
        else None
    )
    return html.Div(
        [
            html.Div(f"Job {snapshot.get('job_id', '')}", className="ds-job__id"),
            stage_progress(
                str(snapshot.get("stage", "Working")),
                completed=snapshot.get("completed_units"),
                total=snapshot.get("total_units"),
            ),
            cancel,
        ],
        className=f"ds-job ds-job--{status}",
        **{"data-job-id": snapshot.get("job_id", "")},
    )


def section_error(message: str, *, retry_id=None, technical_id: str | None = None):
    return retry_panel(message, retry_id=retry_id, technical_id=technical_id)


def stale_data_notice(message: str = "Showing the last successful result while an update runs."):
    return alert(message, tone="warning", title="Updating cached data")


def partial_data_notice(missing_sections: list[str] | tuple[str, ...]):
    names = ", ".join(missing_sections) if missing_sections else "optional sections"
    return alert(
        f"Available results are usable. Still unavailable: {names}.",
        tone="warning",
        title="Partial results",
    )


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
