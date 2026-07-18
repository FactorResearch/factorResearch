"""Dedicated pricing tab and reusable upgrade prompt UI."""

from __future__ import annotations

import time

from dash import Input, Output, callback, html

from codes.app_modules.design_system.primitives import link
from codes.app_modules.session import get_user_id
from codes.services import billing_service, pricing, product_analytics


def build_upgrade_prompt(*, title: str, body: str, source: str, feature: str) -> html.Div:
    return html.Div(
        className="scorecard mt-16",
        children=[
            html.Div("Upgrade to continue", className="scorecard-header"),
            html.Div(
                className="p-20",
                children=[
                    html.H3(title, className="mt-0 mb-8"),
                    html.P(body, className="clr-muted mb-16"),
                    html.Div(
                        className="d-flex gap-12 flex-wrap",
                        children=[
                            link("Compare plans", href="/pricing", className="analyze-btn"),
                            html.A(
                                "Start Premium",
                                href=billing_service.get_entry_url(
                                    plan="premium",
                                    source=source,
                                    feature=feature,
                                ),
                                className="load-btn link-reset",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def build_pricing_tab(context: dict | None = None) -> html.Div:
    context = context or {}
    feature = context.get("feature_label") or "Premium features"
    reason = context.get("reason") or "Choose a plan to unlock the full workflow."
    source = context.get("source") or "pricing_tab"

    cards = []
    for plan in pricing.plan_catalog():
        cta = html.Span("Current plan", className="clr-muted fs-12")
        if plan["key"] == pricing.PREMIUM:
            cta = html.A(
                f"Choose {plan['name']}",
                href=billing_service.get_entry_url(
                    plan=pricing.PREMIUM,
                    source="pricing_tab",
                    feature="subscription",
                ),
                className="analyze-btn d-inline-block mt-12 link-reset",
            )
        cards.append(
            html.Div(
                className="scorecard pricing-card-fill",
                children=[
                    html.Div(plan["name"], className="scorecard-header"),
                    html.Div(
                        className="p-20",
                        children=[
                            html.Div(plan["price"], className="text-2xl font-semibold"),
                            html.Div(plan["subtitle"], className="clr-muted fs-12 mb-16"),
                            html.Ul([html.Li(item) for item in plan["features"]], className="clr-text"),
                            cta,
                        ],
                    ),
                ],
            )
        )

    return html.Div(
        className="main-content",
        children=[
            html.Div(
                className="app-header mb-24",
                children=[
                    html.Div("💳", className="app-header-icon", **{"aria-hidden": "true"}),
                    html.Div(
                        className="app-header-content",
                        children=[
                            html.H1("Pricing"),
                            html.P("A single upgrade path for analysis, backtesting, and portfolio workflow."),
                        ],
                    ),
                ],
            ),
            build_upgrade_prompt(
                title=f"{feature} is locked on your current plan",
                body=reason,
                source=source,
                feature=context.get("feature") or "subscription",
            ),
            html.Div(
                className="pricing-card-grid d-grid gap-20 mt-20",
                children=cards,
            ),
        ],
    )


def open_upgrade_funnel(*, feature: str, feature_label: str, reason: str, source: str) -> dict:
    return {
        "feature": feature,
        "feature_label": feature_label,
        "reason": reason,
        "source": source,
        "nonce": time.time(),
    }


@callback(
    Output("tab-pricing", "children"),
    Input("upgrade-funnel-store", "data"),
    prevent_initial_call=False,
)
def render_pricing_tab(context):
    try:
        product_analytics.track_event(get_user_id(), "pricing_page_viewed", context or {})
    except Exception:
        pass
    return build_pricing_tab(context)
