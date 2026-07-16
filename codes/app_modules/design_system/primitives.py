"""Accessible Dash primitives with consistent states and semantics."""

from typing import Any

from dash import dcc, html


def _classes(base: str, *parts: str | None) -> str:
    return " ".join(filter(None, (base, *parts)))


def button(
    label: Any, *, variant: str = "primary", loading: bool = False, className: str = "", **props
):
    disabled = bool(props.pop("disabled", False) or loading)
    return html.Button(
        [
            html.Span(className="ds-spinner ds-spinner--inline", **{"aria-hidden": "true"}),
            label,
        ],
        className=_classes(
            "ds-button", f"ds-button--{variant}", "is-loading" if loading else None, className
        ),
        disabled=disabled,
        type=props.pop("type", "button"),
        **{"aria-busy": str(loading).lower()},
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


def link(label: Any, href: str, **props):
    return dcc.Link(
        label, href=href, className=_classes("ds-link", props.pop("className", "")), **props
    )


def form_field(
    label: str, control: Any, *, hint: str = "", error: str = "", required: bool = False
):
    control_id = getattr(control, "id", None)
    return html.Div(
        className=_classes("ds-field", "is-error" if error else None),
        children=[
            html.Label(
                [label, html.Span(" *", **{"aria-hidden": "true"}) if required else None],
                htmlFor=control_id,
                className="ds-field__label",
            ),
            control,
            html.Div(error or hint, className="ds-field__message", role="alert" if error else None),
        ],
    )


def input_control(*, control_id, value=None, type="text", **props):
    return dcc.Input(
        id=control_id,
        value=value,
        type=type,
        className=_classes("ds-input", props.pop("className", "")),
        **props,
    )


def select_control(*, control_id, options, value=None, **props):
    return dcc.Dropdown(
        id=control_id,
        options=options,
        value=value,
        className=_classes("ds-select", props.pop("className", "")),
        **props,
    )


def checkbox_group(*, control_id, options, value=None, **props):
    return dcc.Checklist(
        id=control_id,
        options=options,
        value=value or [],
        className=_classes("ds-checklist", props.pop("className", "")),
        **props,
    )


def radio_group(*, control_id, options, value=None, **props):
    return dcc.RadioItems(
        id=control_id,
        options=options,
        value=value,
        className=_classes("ds-radio", props.pop("className", "")),
        **props,
    )


def switch(label: str, *, control_id, value=False, **props):
    return dcc.Checklist(
        id=control_id,
        options=[{"label": label, "value": "on"}],
        value=["on"] if value else [],
        className=_classes("ds-switch", props.pop("className", "")),
        **props,
    )


def slider(*, control_id, min, max, value, **props):
    return dcc.Slider(
        id=control_id,
        min=min,
        max=max,
        value=value,
        className=_classes("ds-slider", props.pop("className", "")),
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


def alert(children: Any, *, tone: str = "info", title: str | None = None, **props):
    role = "alert" if tone in {"danger", "warning"} else "status"
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


def skeleton(*, lines: int = 3, label: str = "Loading content"):
    return html.Div(
        [html.Span(className="ds-skeleton__line") for _ in range(max(1, lines))],
        className="ds-skeleton",
        role="status",
        **{"aria-label": label},
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


def empty_state(title: str, message: str, *, action: Any = None, icon: str = "◇"):
    return html.Div(
        [
            html.Span(icon, className="ds-state__icon", **{"aria-hidden": "true"}),
            html.H3(title),
            html.P(message),
            action,
        ],
        className="ds-state ds-state--empty",
    )


def divider():
    return html.Hr(className="ds-divider")


def tabs(children: Any, *, label: str = "Sections"):
    return html.Div(children, className="ds-tabs", role="tablist", **{"aria-label": label})


def segmented_control(children: Any, *, label: str):
    return html.Div(children, className="ds-segmented", role="group", **{"aria-label": label})


def tooltip(text: str, target: Any):
    return html.Span(
        [target, html.Span(text, className="ds-tooltip__content", role="tooltip")],
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


def responsive_table(children: Any, *, label: str):
    return html.Div(
        html.Table(children, className="ds-table"),
        className="ds-table-wrap",
        role="region",
        tabIndex=0,
        **{"aria-label": label},
    )


def modal(title: str, children: Any, *, modal_id: str, open: bool = False):
    return html.Div(
        html.Div(
            [html.H2(title, id=f"{modal_id}-title"), children],
            className="ds-modal__surface",
            role="dialog",
            **{"aria-modal": "true", "aria-labelledby": f"{modal_id}-title"},
        ),
        id=modal_id,
        className=_classes("ds-modal", "is-open" if open else None),
    )


def drawer(title: str, children: Any, *, drawer_id: str, open: bool = False):
    return html.Aside(
        [html.H2(title, id=f"{drawer_id}-title"), children],
        id=drawer_id,
        className=_classes("ds-drawer", "is-open" if open else None),
        role="dialog",
        **{"aria-modal": "true", "aria-labelledby": f"{drawer_id}-title"},
    )


def toast(children: Any, *, tone: str = "info"):
    return html.Div(
        children, className=f"ds-toast ds-toast--{tone}", role="status", **{"aria-live": "polite"}
    )
