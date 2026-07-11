"""Reusable Premium lock prompt for conversion features."""

from dash import html

from codes import billing


def FeatureLockedModal(*, feature: str, source: str) -> html.Div:
    return html.Div(
        className="scorecard mt-16",
        role="dialog",
        children=[
            html.Div("Premium feature", className="scorecard-header"),
            html.Div(
                className="p-20",
                children=[
                    html.H3("Does your strategy actually work?", className="mt-0 mb-8"),
                    html.P("Test your strategy using historical data", className="clr-muted mb-16"),
                    html.A(
                        "Unlock Premium",
                        href=billing.get_billing_entry_url(plan="premium", source=source, feature=feature),
                        className="analyze-btn",
                        style={"textDecoration": "none"},
                    ),
                ],
            ),
        ],
    )
