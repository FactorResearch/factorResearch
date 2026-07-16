"""Responsive composition primitives."""

from dash import html


def _join(base: str, extra: str) -> str:
    return f"{base} {extra}".strip()


def container(children, *, size: str = "content", className: str = "", **props):
    return html.Div(
        children, className=_join(f"ds-container ds-container--{size}", className), **props
    )


def stack(children, *, gap: str = "4", className: str = "", **props):
    if gap not in {"0", "1", "2", "3", "4", "5", "6", "section"}:
        raise ValueError("gap must use the semantic spacing scale")
    return html.Div(children, className=_join(f"ds-stack ds-stack--gap-{gap}", className), **props)


def cluster(children, *, className: str = "", **props):
    return html.Div(children, className=_join("ds-cluster", className), **props)


def dashboard_grid(children, *, minimum: str = "md", className: str = "", **props):
    if minimum not in {"sm", "md", "lg"}:
        raise ValueError("minimum must be sm, md, or lg")
    return html.Div(children, className=_join(f"ds-grid ds-grid--{minimum}", className), **props)


def analysis_grid(children, *, className: str = "", **props):
    return html.Div(children, className=_join("ds-analysis-grid", className), **props)


def page_header(
    title: str, *, eyebrow: str = "", description: str = "", actions=None, className: str = ""
):
    return html.Header(
        [
            html.Div(
                [
                    html.Div(eyebrow, className="ds-page-header__eyebrow") if eyebrow else None,
                    html.H1(title),
                    html.P(description) if description else None,
                ]
            ),
            html.Div(actions, className="ds-page-header__actions") if actions else None,
        ],
        className=_join("ds-page-header", className),
    )


def split_layout(main, sidebar, *, sticky: bool = False):
    return html.Div(
        [
            html.Main(main),
            html.Aside(sidebar, className="ds-split__sidebar" + (" is-sticky" if sticky else "")),
        ],
        className="ds-split",
    )


def mobile_action_bar(children):
    return html.Div(children, className="ds-mobile-actions")
