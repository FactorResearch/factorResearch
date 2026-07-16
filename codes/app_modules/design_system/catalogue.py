"""Project-native component workshop used by tests and local development."""

from dash import html

from .financial import data_freshness, delta, metric_value, missing_data, model_verdict, score_badge
from .layouts import container, dashboard_grid, page_header, stack
from .primitives import (
    alert,
    badge,
    banner,
    button,
    card,
    confirmation_dialog,
    empty_state,
    form_field,
    input_control,
    progress,
    retry_panel,
    search_control,
    select_control,
    skeleton,
    tab,
    tabs,
    toast,
    tooltip,
)
from .schemas import InteractionState, SectionState, UIState
from .states import analysis_section, partial_data_notice, stale_data_notice


def build_catalogue(*, theme: str = "dark", viewport: str = "desktop"):
    """Render representative variants without registering application callbacks."""
    field = form_field(
        "Ticker",
        input_control(
            control_id=f"catalogue-ticker-{theme}-{viewport}",
            value="BRK.B",
        ),
        hint="Long labels and localized values remain associated with their control.",
    )
    interaction_examples = [
        button(
            state.value.replace("-", " ").title(),
            state=state,
            id=f"catalogue-button-{theme}-{viewport}-{state.value}",
        )
        for state in InteractionState
    ]
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
                        eyebrow="ISSUE_069",
                        description="Keyboard, touch, theme, responsive, financial-edge-case, overlay, and complete interaction-state reference.",
                    ),
                    card(
                        stack(
                            [
                                html.H2("Primitives"),
                                html.Div(
                                    interaction_examples,
                                    className="ds-cluster",
                                ),
                                field,
                                search_control(
                                    control_id=f"catalogue-search-{theme}-{viewport}",
                                    button_id=f"catalogue-search-button-{theme}-{viewport}",
                                    value="Berkshire Hathaway Class B — exceptionally long company name",
                                ),
                                form_field(
                                    "Currency",
                                    select_control(
                                        control_id=f"catalogue-currency-{theme}-{viewport}",
                                        options=[
                                            {"label": "US dollar (USD)", "value": "USD"},
                                            {"label": "Canadian dollar (CAD)", "value": "CAD"},
                                        ],
                                        value="USD",
                                    ),
                                ),
                                tabs(
                                    [
                                        tab(
                                            "Overview",
                                            tab_id=f"catalogue-tab-a-{theme}-{viewport}",
                                            selected=True,
                                        ),
                                        tab(
                                            "Financial health",
                                            tab_id=f"catalogue-tab-b-{theme}-{viewport}",
                                        ),
                                    ],
                                    label="Catalogue sections",
                                ),
                                tooltip(
                                    "Supplementary explanation also available on focus and touch.",
                                    button("Explain score", variant="secondary"),
                                    tooltip_id=f"catalogue-tooltip-{theme}-{viewport}",
                                ),
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
                                banner(
                                    "System is operating with delayed market data.",
                                    tone="warning",
                                    title="Degraded data",
                                ),
                                stale_data_notice(),
                                partial_data_notice(["historical charts", "sector comparison"]),
                                retry_panel(
                                    "The provider did not return this optional section.",
                                    retry_id=f"catalogue-retry-{theme}-{viewport}",
                                    technical_id="catalogue-correlation-id",
                                ),
                                progress(62, label="Catalogue progress"),
                                progress(None, label="Indeterminate catalogue progress"),
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
                                        metric_value(
                                            "CAD market value",
                                            -9876543210.55,
                                            kind="currency",
                                            unit=" CAD",
                                        ),
                                        metric_value("Unavailable estimate", None, kind="currency"),
                                        score_badge(82),
                                        model_verdict("strong_buy"),
                                        delta(-4.2),
                                        delta(0),
                                        data_freshness(None, source="SEC"),
                                        missing_data("Not applicable for this security type"),
                                    ]
                                ),
                            ]
                        )
                    ),
                    card(
                        stack(
                            [
                                html.H2("Overlays, destructive actions, and notifications"),
                                html.P(
                                    "High-impact deletion requires explicit confirmation; reversible actions should use undo feedback."
                                ),
                                html.Div(
                                    [
                                        button("Delete account", variant="danger"),
                                        button(
                                            "Undo portfolio removal",
                                            variant="secondary",
                                            state=InteractionState.SUCCESS,
                                        ),
                                    ],
                                    className="ds-cluster",
                                ),
                                toast(
                                    "Portfolio saved. Undo remains available in context.",
                                    tone="info",
                                ),
                                confirmation_dialog(
                                    "Delete account?",
                                    "This permanently removes saved research and cannot be undone.",
                                    modal_id=f"catalogue-confirm-{theme}-{viewport}",
                                    confirm_id=f"catalogue-confirm-button-{theme}-{viewport}",
                                    cancel_id=f"catalogue-cancel-button-{theme}-{viewport}",
                                    open=False,
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
