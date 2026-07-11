"""Reusable usage banner for Free-plan analysis limits."""

from dash import dcc, html

from codes import billing


def UpgradeBanner(*, remaining: int, limit: int = 3) -> html.Div:
    used = max(limit - remaining, 0)
    return html.Div(
        className="scorecard mt-16",
        children=[
            html.Div(f"{used}/{limit} free analyses used", className="scorecard-header"),
            html.Div(
                className="p-20 d-flex gap-12 flex-wrap",
                children=[
                    html.Span(f"{remaining} free analyses remaining", className="clr-muted"),
                    dcc.Link("Unlock Premium", href=billing.get_billing_entry_url(
                        plan="premium", source="analysis_usage_banner", feature="analysis"
                    ), className="analyze-btn"),
                ],
            ),
        ],
    )
