"""Accessible Dash primitives with consistent states and semantics."""

from typing import Any

from dash import dcc, html

from .schemas import InteractionState


def _classes(base: str, *parts: str | None) -> str:
    return " ".join(filter(None, (base, *parts)))


def button(
    label: Any = None,
    *,
    variant: str = "primary",
    loading: bool = False,
    state: InteractionState | str = InteractionState.DEFAULT,
    selected: bool = False,
    read_only: bool = False,
    className: str = "",
    **props,
):
    label = props.pop("children", label)
    state = InteractionState(state)
    loading = loading or state == InteractionState.LOADING
    read_only = read_only or state == InteractionState.READ_ONLY
    disabled = bool(
        props.pop("disabled", False)
        or loading
        or state in {InteractionState.DISABLED, InteractionState.READ_ONLY}
    )
    aria = {"aria-busy": str(loading).lower(), "data-state": state.value}
    if selected:
        aria["aria-pressed"] = "true"
    return html.Button(
        [html.Span(className="ds-spinner ds-spinner--inline", **{"aria-hidden": "true"}), label]
        if loading
        else label,
        className=_classes(
            "ds-button",
            f"ds-button--{variant}",
            f"is-{state.value}",
            "is-loading" if loading else None,
            className,
        ),
        disabled=disabled,
        type=props.pop("type", "button"),
        **aria,
        **props,
    )


def icon_button(icon: Any, label: str, **props):
    return button(
        icon,
        variant=props.pop("variant", "ghost"),
        className="ds-button--icon",
        **{"aria-label": label},
        **props,
    )


def link(
    label: Any, href: str, *, state: InteractionState | str = InteractionState.DEFAULT, **props
):
    state = InteractionState(state)
    return dcc.Link(
        label,
        href=href,
        className=_classes("ds-link", f"is-{state.value}", props.pop("className", "")),
        **props,
    )


def form_field(
    label: str, control: Any, *, hint: str = "", error: str = "", required: bool = False
):
    control_id = getattr(control, "id", None)
    message_id = f"{control_id}-message" if control_id else None
    return html.Div(
        className=_classes("ds-field", "is-error" if error else None),
        **{"data-required": str(required).lower()},
        children=[
            html.Label(
                [label, html.Span(" *", **{"aria-hidden": "true"}) if required else None],
                htmlFor=control_id,
                className="ds-field__label",
            ),
            control,
            html.Div(
                error or hint,
                id=message_id,
                className="ds-field__message",
                role="alert" if error else None,
            ),
        ],
    )


def input_control(
    *,
    control_id=None,
    value=None,
    type="text",
    state: InteractionState | str = InteractionState.DEFAULT,
    **props,
):
    control_id = props.pop("id", control_id)
    state = InteractionState(state)
    if state == InteractionState.DISABLED:
        props["disabled"] = True
    if state == InteractionState.READ_ONLY:
        props["readOnly"] = True
    return dcc.Input(
        id=control_id,
        value=value,
        type=type,
        className=_classes("ds-input", f"is-{state.value}", props.pop("className", "")),
        **props,
    )


def search_control(*, control_id, button_id, value=None, label: str = "Search", **props):
    return html.Div(
        [
            html.Label(label, htmlFor=control_id, className="sr-only"),
            input_control(
                control_id=control_id,
                value=value,
                type="search",
                **props,
            ),
            button("Search", id=button_id, variant="secondary"),
        ],
        className="ds-search",
        role="search",
    )


def select_control(
    *,
    control_id=None,
    options=None,
    value=None,
    state: InteractionState | str = InteractionState.DEFAULT,
    **props,
):
    control_id = props.pop("id", control_id)
    state = InteractionState(state)
    if state in {InteractionState.DISABLED, InteractionState.READ_ONLY}:
        props["disabled"] = True
    return dcc.Dropdown(
        id=control_id,
        options=options,
        value=value,
        className=_classes("ds-select", f"is-{state.value}", props.pop("className", "")),
        **props,
    )


def checkbox_group(
    *,
    control_id=None,
    options,
    value=None,
    state: InteractionState | str = InteractionState.DEFAULT,
    **props,
):
    control_id = props.pop("id", control_id)
    state = InteractionState(state)
    return dcc.Checklist(
        id=control_id,
        options=options,
        value=value or [],
        className=_classes("ds-checklist", f"is-{state.value}", props.pop("className", "")),
        inline=props.pop("inline", False),
        **props,
    )


def radio_group(
    *,
    control_id=None,
    options,
    value=None,
    state: InteractionState | str = InteractionState.DEFAULT,
    **props,
):
    control_id = props.pop("id", control_id)
    state = InteractionState(state)
    return dcc.RadioItems(
        id=control_id,
        options=options,
        value=value,
        className=_classes("ds-radio", f"is-{state.value}", props.pop("className", "")),
        **props,
    )


def switch(
    label: str,
    *,
    control_id=None,
    value=False,
    state: InteractionState | str = InteractionState.DEFAULT,
    **props,
):
    control_id = props.pop("id", control_id)
    state = InteractionState(state)
    return dcc.Checklist(
        id=control_id,
        options=[{"label": label, "value": "on"}],
        value=["on"] if value else [],
        className=_classes("ds-switch", f"is-{state.value}", props.pop("className", "")),
        **props,
    )


def slider(
    *,
    control_id=None,
    min,
    max,
    value,
    state: InteractionState | str = InteractionState.DEFAULT,
    **props,
):
    control_id = props.pop("id", control_id)
    state = InteractionState(state)
    if state in {InteractionState.DISABLED, InteractionState.READ_ONLY}:
        props["disabled"] = True
    # Dash's Radix thumb is clipped below WCAG's target minimum at narrow widths.
    # A number input preserves exact min/max/step editing and native arrow-key behavior.
    props.pop("marks", None)
    props.pop("tooltip", None)
    props.pop("allow_direct_input", None)
    return dcc.Input(
        id=control_id,
        type="number",
        min=min,
        max=max,
        step=props.pop("step", 1),
        value=value,
        className=_classes("ds-slider", f"is-{state.value}", props.pop("className", "")),
        **props,
    )


def card(children: Any, *, elevated: bool = False, className: str = "", **props):
    return html.Section(
        children=children,
        className=_classes("ds-card", "ds-card--raised" if elevated else None, className),
        **props,
    )


def badge(label: Any, *, tone: str = "neutral", **props):
    return html.Span(
        label,
        className=_classes("ds-badge", f"ds-badge--{tone}", props.pop("className", "")),
        **props,
    )


def alert(
    children: Any,
    *,
    tone: str = "info",
    title: str | None = None,
    urgent: bool = False,
    **props,
):
    role = "alert" if urgent else "status"
    return html.Div(
        [html.Strong(title, className="ds-alert__title") if title else None, children],
        className=f"ds-alert ds-alert--{tone}",
        role=role,
        **props,
    )


def status_region(children: Any = None, *, atomic: bool = True, **props):
    return html.Div(
        children,
        className=_classes("ds-status-region", props.pop("className", "")),
        role="status",
        **{"aria-live": "polite", "aria-atomic": str(atomic).lower()},
        **props,
    )


def loading_container(children: Any = None, *, label: str = "Updating content", **props):
    """Shared delayed Dash loader; callers retain control of the smallest useful scope."""
    children = props.pop("children", children)
    return dcc.Loading(
        children=children,
        delay_show=props.pop("delay_show", 250),
        delay_hide=props.pop("delay_hide", 200),
        show_initially=props.pop("show_initially", False),
        type=props.pop("type", "default"),
        **props,
    )


def skeleton(*, lines: int = 3, label: str = "Loading content", decorative: bool = True):
    semantics = {"aria-hidden": "true"} if decorative else {"role": "status", "aria-label": label}
    return html.Div(
        [html.Span(className="ds-skeleton__line") for _ in range(max(1, lines))],
        className="ds-skeleton",
        **semantics,
    )


def progress(value: int | None = None, *, label: str = "Loading"):
    attrs = {"aria-label": label, "aria-valuemin": "0", "aria-valuemax": "100"}
    if value is not None:
        attrs["aria-valuenow"] = str(value)
    return html.Progress(
        value=value,
        max=100,
        className="ds-progress",
        role="progressbar",
        **attrs,
    )


def empty_state(
    title: str,
    message: str,
    *,
    action: Any = None,
    icon: str = "◇",
    state: str = "empty",
):
    return html.Div(
        [
            html.Span(icon, className="ds-state__icon", **{"aria-hidden": "true"}),
            html.H3(title),
            html.P(message),
            action,
        ],
        className=f"ds-state ds-state--{state}",
        **{"data-state": state},
    )


def divider():
    return html.Hr(className="ds-divider")


def tabs(children: Any, *, label: str = "Sections"):
    return html.Div(children, className="ds-tabs", role="tablist", **{"aria-label": label})


def tab(label: Any, *, tab_id, selected: bool = False, panel_id: str | None = None, **props):
    attrs = {
        "role": "tab",
        "aria-selected": str(selected).lower(),
        "tabIndex": 0 if selected else -1,
    }
    if panel_id:
        attrs["aria-controls"] = panel_id
    return button(
        label,
        id=tab_id,
        variant="ghost",
        state=InteractionState.SELECTED if selected else InteractionState.DEFAULT,
        **attrs,
        **props,
    )


def segmented_control(children: Any, *, label: str):
    return html.Div(children, className="ds-segmented", role="group", **{"aria-label": label})


def tooltip(text: str, target: Any, *, tooltip_id: str):
    return html.Span(
        [
            html.Span(
                target,
                className="ds-tooltip__trigger",
                tabIndex=0,
                **{"aria-describedby": tooltip_id},
            ),
            html.Span(text, id=tooltip_id, className="ds-tooltip__content", role="tooltip"),
        ],
        className="ds-tooltip",
    )


def popover(trigger: Any, content: Any, *, open: bool = False):
    return html.Div(
        [trigger, html.Div(content, className="ds-popover__content", hidden=not open)],
        className="ds-popover",
    )


def menu(items: Any, *, label: str):
    return html.Div(items, className="ds-menu", role="menu", **{"aria-label": label})


def pagination(current: int, total: int, *, previous_id, next_id):
    return html.Nav(
        [
            button("Previous", id=previous_id, variant="secondary", disabled=current <= 1),
            html.Span(f"Page {current} of {total}", **{"aria-live": "polite"}),
            button("Next", id=next_id, variant="secondary", disabled=current >= total),
        ],
        className="ds-pagination",
        **{"aria-label": "Pagination"},
    )


def responsive_table(
    children: Any,
    *,
    label: str,
    density: str = "comfortable",
    sticky_identifier: bool = False,
    className: str = "",
):
    if density not in {"comfortable", "compact"}:
        raise ValueError("density must be comfortable or compact")
    return html.Div(
        [
            html.P(
                "Scroll horizontally for additional financial columns.",
                className="ds-table-scroll-cue",
            ),
            table(
                children,
                caption=label,
                className=_classes(className, f"density-{density}"),
            ),
        ],
        className=_classes(
            "ds-table-wrap",
            "has-sticky-identifier" if sticky_identifier else None,
        ),
        role="region",
        tabIndex=0,
        **{
            "aria-label": label,
            "data-responsive-table": "true",
            "data-table-density": density,
        },
    )


def _scope_table_headers(node: Any) -> None:
    if isinstance(node, (list, tuple)):
        for child in node:
            _scope_table_headers(child)
        return
    if getattr(node, "_type", "") == "Th" and not getattr(node, "scope", None):
        node.scope = "col"
    children = getattr(node, "children", None)
    if children is not None:
        _scope_table_headers(children)


def table(children: Any = None, *, caption: str = "", className: str = "", **props):
    children = props.pop("children", children)
    _scope_table_headers(children)
    if caption:
        if isinstance(children, (list, tuple)):
            children = [html.Caption(caption, className="sr-only"), *children]
        else:
            children = [html.Caption(caption, className="sr-only"), children]
    return html.Table(
        children,
        className=_classes("ds-table", className),
        **props,
    )


def modal(
    title: str,
    children: Any,
    *,
    modal_id: str,
    open: bool = False,
    close_id=None,
):
    return html.Div(
        html.Div(
            [
                html.Div(
                    [
                        html.H2(title, id=f"{modal_id}-title"),
                        icon_button(
                            "×",
                            "Close dialog",
                            id=close_id,
                            **{"data-ds-close": "true"},
                        )
                        if close_id
                        else None,
                    ],
                    className="ds-dialog__header",
                ),
                children,
            ],
            className="ds-modal__surface",
            role="dialog",
            **{"aria-modal": "true", "aria-labelledby": f"{modal_id}-title"},
        ),
        id=modal_id,
        className=_classes("ds-modal", "is-open" if open else None),
        hidden=not open,
        **{"data-ds-overlay": "modal"},
    )


def drawer(title: str, children: Any, *, drawer_id: str, open: bool = False):
    return html.Aside(
        [html.H2(title, id=f"{drawer_id}-title"), children],
        id=drawer_id,
        className=_classes("ds-drawer", "is-open" if open else None),
        hidden=not open,
        role="dialog",
        **{
            "aria-modal": "true",
            "aria-labelledby": f"{drawer_id}-title",
            "data-ds-overlay": "drawer",
        },
    )


def toast(children: Any, *, tone: str = "info", dismiss_id=None):
    return html.Div(
        [children, icon_button("×", "Dismiss notification", id=dismiss_id) if dismiss_id else None],
        className=f"ds-toast ds-toast--{tone}",
        role="status",
        **{"aria-live": "polite"},
    )


def banner(children: Any, *, tone: str = "info", title: str | None = None):
    return html.Section(
        [html.Strong(title, className="ds-banner__title") if title else None, children],
        className=f"ds-banner ds-banner--{tone}",
        role="status",
    )


def retry_panel(message: str, *, retry_id=None, technical_id: str | None = None):
    details = (
        html.Details(
            [html.Summary("Technical details"), html.Code(technical_id)],
            className="ds-error__technical",
        )
        if technical_id
        else None
    )
    return alert(
        [
            html.P(message),
            button("Try again", id=retry_id, variant="secondary") if retry_id else None,
            details,
        ],
        tone="danger",
        title="Unable to complete this section",
    )


def confirmation_dialog(
    title: str,
    message: str,
    *,
    modal_id: str,
    confirm_id,
    cancel_id,
    open: bool = False,
    confirmation_label: str = "Confirm destructive action",
):
    return modal(
        title,
        [
            html.P(message),
            html.Div(
                [
                    button(
                        "Cancel",
                        id=cancel_id,
                        variant="secondary",
                        **{"data-ds-close": "true"},
                    ),
                    button(
                        confirmation_label,
                        id=confirm_id,
                        variant="danger",
                    ),
                ],
                className="ds-dialog__actions",
            ),
        ],
        modal_id=modal_id,
        open=open,
    )
