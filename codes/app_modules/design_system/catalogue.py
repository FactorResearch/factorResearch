"""Project-native component workshop used by tests and local development."""

from dash import dcc, html

from .financial import data_freshness, delta, metric_value, model_verdict, score_badge
from .layouts import container, dashboard_grid, page_header, stack
from .primitives import alert, badge, button, card, empty_state, form_field, progress, skeleton
from .schemas import SectionState, UIState
from .states import analysis_section


def build_catalogue(*, theme: str = "dark", viewport: str = "desktop"):
    """Render representative variants without registering application callbacks."""
    field = form_field(
        "Ticker",
        dcc.Input(id=f"catalogue-ticker-{theme}-{viewport}", value="BRK.B", className="ds-input"),
        hint="Long labels and localized values remain associated with their control.",
    )
    state_examples = [
        analysis_section(
            state.value.replace("_", " ").title(),
            card("Representative section content"),
            SectionState(
                state,
                f"{state.value} announcement",
                progress=48 if state in {UIState.LOADING, UIState.REFRESHING} else None,
                stale_content=card("Last known data")
                if state in {UIState.REFRESHING, UIState.STALE, UIState.PARTIAL}
                else None,
            ),
            section_id=f"catalogue-{theme}-{viewport}-{state.value}",
            optional=state in {UIState.PARTIAL, UIState.UNAVAILABLE},
        )
        for state in UIState
    ]
    return html.Div(
        container(
            stack(
                [
                    page_header(
                        "Design engine catalogue",
                        eyebrow="ISSUE_075",
                        description="Keyboard, theme, responsive, long-text, and asynchronous-state reference.",
                    ),
                    card(
                        stack(
                            [
                                html.H2("Primitives"),
                                html.Div(
                                    [
                                        button("Primary action"),
                                        button("Secondary action", variant="secondary"),
                                        button("Working", loading=True),
                                        button("Disabled", disabled=True),
                                    ],
                                    className="ds-cluster",
                                ),
                                field,
                                html.Div(
                                    [
                                        badge("Neutral"),
                                        badge("Positive", tone="positive"),
                                        badge("Warning", tone="warning"),
                                        badge("Danger", tone="danger"),
                                    ],
                                    className="ds-cluster",
                                ),
                                alert("Informational notice", tone="info"),
                                alert("Recoverable warning", tone="warning"),
                                progress(62, label="Catalogue progress"),
                                skeleton(lines=2),
                                empty_state(
                                    "Nothing to show", "This is the shared empty-state treatment."
                                ),
                            ]
                        )
                    ),
                    card(
                        stack(
                            [
                                html.H2("Financial meaning"),
                                dashboard_grid(
                                    [
                                        metric_value(
                                            "Market capitalization", 245600000000, kind="compact"
                                        ),
                                        score_badge(82),
                                        model_verdict("strong_buy"),
                                        delta(-4.2),
                                        data_freshness(None, source="SEC"),
                                    ]
                                ),
                            ]
                        )
                    ),
                    html.Div(state_examples),
                ]
            ),
            size="wide",
        ),
        className=f"ds-catalogue ds-catalogue--{viewport}",
        **{"data-theme": theme, "data-viewport": viewport},
    )


def catalogue_matrix():
    return [
        build_catalogue(theme=theme, viewport=viewport)
        for theme in ("light", "dark")
        for viewport in ("mobile", "desktop")
    ]
