"""Profile page callbacks and helpers."""

from __future__ import annotations

import dash
from dash import Input, Output, State, callback, html

from codes.app_modules.design_system.primitives import button
from codes.app_modules.screener_markets import market_from_path
from codes.app_modules.session import get_user_id
from codes.services import account_service


def _display_name() -> str:
    return account_service.display_name(get_user_id())


def _selected_notifications(settings: dict) -> list[str]:
    return [
        key
        for key, enabled in (settings.get("notifications") or {}).items()
        if enabled
    ]


def _portfolio_rows(user_id: str):
    portfolios = account_service.portfolio_summaries(user_id)
    if not portfolios:
        return html.Div("No saved portfolios yet.", className="text-muted")
    return html.Ul(
        [
            html.Li(
                f"{item['name']} · {item['holdings']} holdings"
            )
            for item in portfolios
        ],
        className="mb-0",
    )


def _saved_screener_rows(settings: dict):
    screeners = settings.get("saved_screeners") or []
    if not screeners:
        return html.Div("No saved screeners yet.", className="text-muted")
    return html.Ul(
        [
            html.Li(
                f"{item['name']} · {item['market']}"
                + (f" · sector {item['sector']}" if item.get("sector") else "")
                + (f" · indexes {', '.join(item['indexes'])}" if item.get("indexes") else "")
            )
            for item in screeners
        ],
        className="mb-0",
    )


def _subscription_summary(user_id: str):
    subscription = account_service.subscription_summary(user_id)
    plan = subscription["plan"].capitalize()
    status = subscription["status"].replace("_", " ").capitalize()
    usage = subscription["trial_usage"]
    return html.Div(
        [
            html.P(f"Plan: {plan}", className="mb-6"),
            html.P(f"Status: {status}", className="mb-6"),
            html.P(f"Trial analyses used: {usage}", className="mb-12"),
            html.A(
                "Manage subscription" if subscription["paid"] else "Upgrade to Premium",
                href=account_service.billing_entry_url(user_id),
                className="analyze-btn",
            ),
        ]
    )


def _quick_section_content(section_key: str, settings: dict, user_id: str):
    provider = account_service.auth_provider()
    sections = {
        "account": (
            "Account identity and provider context.",
            html.Div([
                html.P(f"User ID: {user_id}", className="mb-6"),
                html.P(f"Auth provider: {provider}", className="mb-0"),
            ]),
        ),
        "subscription": (
            "Plan status, usage, and billing access.",
            _subscription_summary(user_id),
        ),
        "appearance": (
            "Theme is stored per account.",
            html.Div([
                html.P(f"Current theme: {settings['appearance']['theme'].capitalize()}", className="mb-0"),
            ]),
        ),
        "notifications": (
            "Notification preferences are stored per account.",
            html.Div([
                html.P(
                    "Enabled: " + ", ".join(label.replace("_", " ") for label in _selected_notifications(settings))
                    if _selected_notifications(settings) else "Enabled: none",
                    className="mb-0",
                )
            ]),
        ),
        "portfolios": (
            "Saved portfolios for this account.",
            _portfolio_rows(user_id),
        ),
        "screeners": (
            "Saved screener presets for this account.",
            _saved_screener_rows(settings),
        ),
        "security": (
            "Password and account actions.",
            html.Div([
                html.P("Password and MFA are managed by your authentication provider.", className="mb-6"),
                html.Div([
                    html.A("Log out", href="/logout", className="load-btn"),
                    html.Form(
                        action="/account/delete",
                        method="post",
                        children=[button("Delete account", type="submit", variant="danger", className="load-btn portfolio-delete-btn")],
                    ),
                ], className="d-flex gap-12 flex-wrap"),
            ]),
        ),
    }
    return sections.get(section_key, sections["appearance"])


@callback(
    Output("user-settings-store", "data"),
    Input("url", "pathname"),
    prevent_initial_call=False,
)
def load_user_settings(_pathname):
    return account_service.get_settings(get_user_id())


@callback(
    Output("profile-menu-label", "children"),
    Input("url", "pathname"),
    prevent_initial_call=False,
)
def render_profile_menu_label(_pathname):
    return f"Hi {_display_name()}"


@callback(
    Output("profile-quick-panel", "className"),
    Output("profile-menu-chevron", "children"),
    Input("profile-menu-btn", "n_clicks"),
    Input("url", "pathname"),
    State("profile-quick-panel", "className"),
    prevent_initial_call=False,
)
def toggle_profile_quick_panel(n_clicks, pathname, current_class):
    if pathname == "/profile":
        return "scorecard is-hidden", "▾"
    triggered = dash.ctx.triggered_id
    if triggered == "profile-menu-btn" and n_clicks:
        is_opening = "is-hidden" in str(current_class or "")
        return ("scorecard profile-quick-panel" if is_opening else "scorecard profile-quick-panel is-hidden"), ("▴" if is_opening else "▾")
    current = current_class or "scorecard profile-quick-panel is-hidden"
    is_hidden = "is-hidden" in current
    normalized = current if "profile-quick-panel" in current else f"{current} profile-quick-panel".strip()
    return normalized, ("▾" if is_hidden else "▴")


@callback(
    Output("profile-quick-theme-dropdown", "value"),
    Output("profile-quick-summary", "children"),
    Output("profile-quick-detail", "children"),
    Input("user-settings-store", "data"),
    Input("portfolio-refresh-store", "data"),
    Input("profile-quick-section-dropdown", "value"),
    prevent_initial_call=False,
)
def render_profile_quick_panel(settings_data, _portfolio_refresh, section_key):
    settings = account_service.normalize_settings(settings_data)
    summary, detail = _quick_section_content(section_key or "appearance", settings, get_user_id())
    return settings["appearance"]["theme"], summary, detail


@callback(
    Output("user-settings-store", "data", allow_duplicate=True),
    Output("profile-quick-msg", "children"),
    Input("profile-quick-save-btn", "n_clicks"),
    State("profile-quick-theme-dropdown", "value"),
    prevent_initial_call=True,
)
def save_profile_quick_settings(n_clicks, theme):
    if not n_clicks:
        return dash.no_update, dash.no_update
    settings = account_service.update_settings(
        get_user_id(),
        {"appearance": {"theme": theme}},
    )
    return settings, "Quick settings saved."


@callback(
    Output("profile-section-summary", "children"),
    Output("profile-theme-dropdown", "value"),
    Output("profile-notifications-checklist", "value"),
    Output("profile-saved-screener-select", "options"),
    Output("profile-saved-screener-select", "value"),
    Output("profile-screeners-panel", "className"),
    Output("profile-saved-screeners-card", "children"),
    Output("profile-detail-card", "children"),
    Input("user-settings-store", "data"),
    Input("portfolio-refresh-store", "data"),
    Input("profile-section-dropdown", "value"),
    prevent_initial_call=False,
)
def render_profile(settings_data, _portfolio_refresh, active_section):
    settings = account_service.normalize_settings(settings_data)
    user_id = get_user_id()
    provider = account_service.auth_provider()
    account = html.Div(
        [
            html.P(f"User ID: {user_id}", className="mb-6"),
            html.P(f"Auth provider: {provider}", className="mb-6"),
            html.P(f"Theme setting: {settings['appearance']['theme'].capitalize()}", className="mb-0"),
        ]
    )
    security = html.Div(
        [
            html.P("Password and MFA are managed by your authentication provider.", className="mb-6"),
            html.P("Account deletion is available from the authenticated delete endpoint.", className="mb-12"),
            html.Div(
                [
                    html.A("Log out", href="/logout", className="load-btn"),
                    html.Form(
                        action="/account/delete",
                        method="post",
                        children=[button("Delete account", type="submit", variant="danger", className="load-btn portfolio-delete-btn")],
                    ),
                ],
                className="d-flex gap-12 flex-wrap",
            ),
        ]
    )
    appearance = html.Div(
        [
            html.P("Theme is now a per-account preference.", className="mb-6"),
            html.P(f"Current theme: {settings['appearance']['theme'].capitalize()}", className="mb-0"),
        ]
    )
    notifications = html.Div(
        [
            html.P("Notification preferences are stored per account.", className="mb-6"),
            html.P(
                "Enabled: " + ", ".join(label.replace("_", " ") for label in _selected_notifications(settings))
                if _selected_notifications(settings) else "Enabled: none",
                className="mb-0",
            ),
        ]
    )
    api_keys = html.Div("Reserved in the per-account settings document for future API key management.", className="text-muted")
    screener_options = [
        {"label": item["name"], "value": item["id"]}
        for item in settings.get("saved_screeners") or []
    ]
    sections = {
        "account": ("Account", "Account identity and auth provider details.", account),
        "subscription": ("Subscription", "Plan status, usage, and billing access.", _subscription_summary(user_id)),
        "appearance": ("Appearance", "Theme now lives under user settings for ISSUE_044.", appearance),
        "notifications": ("Notifications", "Per-account notification preferences.", notifications),
        "portfolios": ("Saved portfolios", "Portfolio assets stored for this account.", _portfolio_rows(user_id)),
        "screeners": (
            "Saved screeners",
            "Save or remove reusable screener presets for this account.",
            html.Div("Use the screener panel above to manage reusable presets."),
        ),
        "security": ("Security", "Password, logout, and account deletion actions.", security),
        "api_keys": ("API keys", "Future API key management placeholder.", api_keys),
    }
    section_key = active_section if active_section in sections else "appearance"
    section_title, section_summary, section_body = sections[section_key]
    return (
        f"{section_title}: {section_summary}",
        settings["appearance"]["theme"],
        _selected_notifications(settings),
        screener_options,
        None,
        "scorecard mb-16" if section_key == "screeners" else "scorecard mb-16 is-hidden",
        _saved_screener_rows(settings),
        [html.Div(section_title, className="scorecard-header"), html.Div(section_body, className="p-16")],
    )


@callback(
    Output("user-settings-store", "data", allow_duplicate=True),
    Output("profile-settings-msg", "children"),
    Input("profile-save-settings-btn", "n_clicks"),
    State("profile-theme-dropdown", "value"),
    State("profile-notifications-checklist", "value"),
    prevent_initial_call=True,
)
def save_profile_settings(n_clicks, theme, notifications):
    if not n_clicks:
        return dash.no_update, dash.no_update
    settings = account_service.save_preferences(
        get_user_id(), theme=theme, notifications=notifications,
    )
    return settings, "Profile settings saved."


@callback(
    Output("user-settings-store", "data", allow_duplicate=True),
    Output("profile-screener-msg", "children"),
    Output("profile-save-screener-name", "value"),
    Input("profile-save-screener-btn", "n_clicks"),
    State("profile-save-screener-name", "value"),
    State("screener-context-store", "data"),
    prevent_initial_call=True,
)
def save_current_screener(n_clicks, name, screener_context):
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update
    screener_context = screener_context or {}
    try:
        settings = account_service.add_saved_screener(
            get_user_id(),
            name=name,
            market=str(screener_context.get("market") or "US"),
            sector=str(screener_context.get("sector") or ""),
            indexes=list(screener_context.get("indexes") or []),
        )
    except ValueError as exc:
        return dash.no_update, str(exc), dash.no_update
    return settings, "Current screener saved.", ""


@callback(
    Output("user-settings-store", "data", allow_duplicate=True),
    Output("profile-screener-msg", "children", allow_duplicate=True),
    Input("profile-delete-screener-btn", "n_clicks"),
    State("profile-saved-screener-select", "value"),
    prevent_initial_call=True,
)
def delete_saved_screener(n_clicks, screener_id):
    if not n_clicks:
        return dash.no_update, dash.no_update
    if not screener_id:
        return dash.no_update, "Select a saved screener to remove."
    return account_service.delete_saved_screener(get_user_id(), screener_id), "Saved screener removed."


@callback(
    Output("screener-context-store", "data"),
    Input("url", "pathname"),
    Input("sector-filter", "value"),
    Input("index-filter", "data"),
    State("screener-context-store", "data"),
    prevent_initial_call=False,
)
def remember_screener_context(pathname, sector, indexes, existing):
    is_screener_route = str(pathname or "").startswith("/screener/")
    existing = existing or {}
    existing_market = market_from_path(pathname).code if is_screener_route else str(existing.get("market") or "US")
    return {
        "market": existing_market,
        "sector": sector if sector is not None else str(existing.get("sector") or ""),
        "indexes": list(indexes if indexes is not None else existing.get("indexes") or []),
    }
