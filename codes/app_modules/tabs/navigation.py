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
    Output("tab-screener",     "style"),
    Output("tab-analyze",      "style"),
    Output("tab-portfolio",    "style"),
    Output("tab-factorlab",    "style"),
    Output("tab-pricing",      "style"),
    Output("tab-screener-btn", "className"),
    Output("tab-analyze-btn",  "className"),
    Output("tab-portfolio-btn","className"),
    Output("tab-factorlab-btn", "className"),
    Output("tab-pricing-btn", "className"),
    Input("tab-screener-btn",     "n_clicks"),
    Input("tab-analyze-btn",      "n_clicks"),
    Input("tab-portfolio-btn",    "n_clicks"),
    Input("tab-factorlab-btn",    "n_clicks"),
    Input("tab-pricing-btn",      "n_clicks"),
    Input("screener-open-analysis-symbol","data"),
    Input("upgrade-funnel-store", "data"),
    Input("url",                  "pathname"),
    prevent_initial_call=False
)
def switch_tabs(n_screener, n_analyze, n_portfolio, n_factorlab, n_pricing, open_analysis_symbol, upgrade_context, pathname):
    triggered = dash.ctx.triggered_id
    SHOW, HIDE = {"display": "block"}, {"display": "none"}
    ACTIVE, IDLE = "topbar-nav-btn tab-btn active", "topbar-nav-btn tab-btn"
    if triggered == "screener-open-analysis-symbol" and open_analysis_symbol:
        return HIDE, SHOW, HIDE, HIDE, HIDE, IDLE, ACTIVE, IDLE, IDLE, IDLE
    if triggered == "upgrade-funnel-store" and upgrade_context:
        return HIDE, HIDE, HIDE, HIDE, SHOW, IDLE, IDLE, IDLE, IDLE, ACTIVE
    if triggered == "tab-screener-btn" and n_screener:
        return SHOW, HIDE, HIDE, HIDE, HIDE, ACTIVE, IDLE, IDLE, IDLE, IDLE
    if triggered == "tab-analyze-btn":
        return HIDE, SHOW, HIDE, HIDE, HIDE, IDLE, ACTIVE, IDLE, IDLE, IDLE
    if triggered == "tab-portfolio-btn":
        return HIDE, HIDE, SHOW, HIDE, HIDE, IDLE, IDLE, ACTIVE, IDLE, IDLE
    if triggered == "tab-factorlab-btn":
        return HIDE, HIDE, HIDE, SHOW, HIDE, IDLE, IDLE, IDLE, ACTIVE, IDLE
    if triggered == "tab-pricing-btn":
        return HIDE, HIDE, HIDE, HIDE, SHOW, IDLE, IDLE, IDLE, IDLE, ACTIVE
    if _ANALYZE_PATH_RE.fullmatch(pathname or ""):
        return HIDE, SHOW, HIDE, HIDE, HIDE, IDLE, ACTIVE, IDLE, IDLE, IDLE
    if (pathname or "") == "/pricing":
        return HIDE, HIDE, HIDE, HIDE, SHOW, IDLE, IDLE, IDLE, IDLE, ACTIVE
    return SHOW, HIDE, HIDE, HIDE, HIDE, ACTIVE, IDLE, IDLE, IDLE, IDLE


# ── Theme Toggle ────────────────────────────────────────────────────────────
def _make_theme_js(target_theme):
    return f"""
    function(n) {{
        if (!n) return "";
        localStorage.setItem("fr-theme", "{target_theme}");
        var light = "{target_theme}" === "light" ||
            ("{target_theme}" === "system" && window.matchMedia("(prefers-color-scheme: light)").matches);
        document.documentElement.classList.toggle("light", light);
        document.body.classList.toggle("light", light);
        document.querySelectorAll(".theme-btn").forEach(function(btn) {{
            btn.classList.toggle("active", btn.dataset.theme === "{target_theme}");
        }});
        return "";
    }}
    """

for btn_id, theme_val in [("theme-light", "light"), ("theme-system", "system"), ("theme-dark", "dark")]:
    clientside_callback(
        _make_theme_js(theme_val),
        Output("theme-dummy", f"data-{theme_val}"),
        Input(btn_id, "n_clicks"),
        prevent_initial_call=True,
    )

clientside_callback(
    """
    function() {
        var theme = localStorage.getItem("fr-theme") || "system";
        var light = theme === "light" ||
            (theme === "system" && window.matchMedia("(prefers-color-scheme: light)").matches);
        document.documentElement.classList.toggle("light", light);
        document.body.classList.toggle("light", light);
        document.querySelectorAll(".theme-btn").forEach(function(btn) {
            btn.classList.toggle("active", btn.dataset.theme === theme);
        });
        return "";
    }
    """,
    Output("theme-dummy", "data-init"),
    Input("theme-toggle", "id"),
    prevent_initial_call=False,
)
