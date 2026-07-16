"""Top-level tab navigation and theme callbacks."""

import re

import dash
from dash import Input, Output, callback, clientside_callback

_ANALYZE_PATH_RE = re.compile(
    r"^(?:/analyze/[A-Za-z]{1,6}(?:/(?:\d{8}|\d{4}-\d{2}-\d{2}))?"
    r"|/[A-Za-z]{1,6}/analyze/(?:\d{8}|\d{4}-\d{2}-\d{2}))/?$"
)


# ── Tab Navigation ───────────────────────────────────────────────────────────
@callback(
    Output("tab-screener", "style"),
    Output("tab-analyze", "style"),
    Output("tab-portfolio", "style"),
    Output("tab-factorlab", "style"),
    Output("tab-pricing", "style"),
    Output("profile-page", "style"),
    Output("tab-screener-btn", "className"),
    Output("tab-analyze-btn", "className"),
    Output("tab-portfolio-btn", "className"),
    Output("tab-factorlab-btn", "className"),
    Output("tab-pricing-btn", "className"),
    Output("profile-menu-btn", "className"),
    Input("tab-screener-btn", "n_clicks"),
    Input("tab-analyze-btn", "n_clicks"),
    Input("tab-portfolio-btn", "n_clicks"),
    Input("tab-factorlab-btn", "n_clicks"),
    Input("tab-pricing-btn", "n_clicks"),
    Input("screener-open-analysis-symbol", "data"),
    Input("upgrade-funnel-store", "data"),
    Input("url", "pathname"),
    prevent_initial_call=False,
)
def switch_tabs(
    n_screener,
    n_analyze,
    n_portfolio,
    n_factorlab,
    n_pricing,
    open_analysis_symbol,
    upgrade_context,
    pathname,
):
    triggered = dash.ctx.triggered_id
    SHOW, HIDE = {"display": "block"}, {"display": "none"}
    ACTIVE, IDLE = "topbar-nav-btn tab-btn active", "topbar-nav-btn tab-btn"
    if (pathname or "") == "/profile":
        return HIDE, HIDE, HIDE, HIDE, HIDE, SHOW, IDLE, IDLE, IDLE, IDLE, IDLE, ACTIVE
    if triggered == "screener-open-analysis-symbol" and open_analysis_symbol:
        return HIDE, SHOW, HIDE, HIDE, HIDE, HIDE, IDLE, ACTIVE, IDLE, IDLE, IDLE, IDLE
    if triggered == "upgrade-funnel-store" and upgrade_context:
        return HIDE, HIDE, HIDE, HIDE, SHOW, HIDE, IDLE, IDLE, IDLE, IDLE, ACTIVE, IDLE
    if triggered == "tab-screener-btn" and n_screener:
        return SHOW, HIDE, HIDE, HIDE, HIDE, HIDE, ACTIVE, IDLE, IDLE, IDLE, IDLE, IDLE
    if triggered == "tab-analyze-btn":
        return HIDE, SHOW, HIDE, HIDE, HIDE, HIDE, IDLE, ACTIVE, IDLE, IDLE, IDLE, IDLE
    if triggered == "tab-portfolio-btn":
        return HIDE, HIDE, SHOW, HIDE, HIDE, HIDE, IDLE, IDLE, ACTIVE, IDLE, IDLE, IDLE
    if triggered == "tab-factorlab-btn":
        return HIDE, HIDE, HIDE, SHOW, HIDE, HIDE, IDLE, IDLE, IDLE, ACTIVE, IDLE, IDLE
    if triggered == "tab-pricing-btn":
        return HIDE, HIDE, HIDE, HIDE, SHOW, HIDE, IDLE, IDLE, IDLE, IDLE, ACTIVE, IDLE
    if _ANALYZE_PATH_RE.fullmatch(pathname or ""):
        return HIDE, SHOW, HIDE, HIDE, HIDE, HIDE, IDLE, ACTIVE, IDLE, IDLE, IDLE, IDLE
    if (pathname or "") == "/pricing":
        return HIDE, HIDE, HIDE, HIDE, SHOW, HIDE, IDLE, IDLE, IDLE, IDLE, ACTIVE, IDLE
    return SHOW, HIDE, HIDE, HIDE, HIDE, HIDE, ACTIVE, IDLE, IDLE, IDLE, IDLE, IDLE


# ── Theme Toggle ────────────────────────────────────────────────────────────
clientside_callback(
    """
    function(settings) {
        var theme = (settings && settings.appearance && settings.appearance.theme) || localStorage.getItem("fr-theme") || "system";
        localStorage.setItem("fr-theme", theme);
        var light = theme === "light" ||
            (theme === "system" && window.matchMedia("(prefers-color-scheme: light)").matches);
        document.documentElement.classList.toggle("light", light);
        document.body.classList.toggle("light", light);
        document.documentElement.dataset.theme = light ? "light" : "dark";
        document.documentElement.dataset.themePreference = theme;
        if (!window.__frThemeListener) {
            window.__frThemeListener = function(event) {
                if ((localStorage.getItem("fr-theme") || "system") !== "system") return;
                document.documentElement.classList.toggle("light", event.matches);
                document.body.classList.toggle("light", event.matches);
                document.documentElement.dataset.theme = event.matches ? "light" : "dark";
            };
            window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", window.__frThemeListener);
        }
        return "";
    }
    """,
    Output("theme-dummy", "data-init"),
    Input("user-settings-store", "data"),
    prevent_initial_call=False,
)
