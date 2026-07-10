"""Top-level tab navigation and theme callbacks."""

import dash
from dash import Input, Output, State, callback, clientside_callback

# ── Tab Navigation ───────────────────────────────────────────────────────────
@callback(
    Output("tab-screener",     "style"),
    Output("tab-analyze",      "style"),
    Output("tab-portfolio",    "style"),
    Output("tab-factorlab",    "style"),
    Output("tab-screener-btn", "className"),
    Output("tab-analyze-btn",  "className"),
    Output("tab-portfolio-btn","className"),
    Output("tab-factorlab-btn", "className"),
    Input("tab-screener-btn",     "n_clicks"),
    Input("tab-analyze-btn",      "n_clicks"),
    Input("tab-portfolio-btn",    "n_clicks"),
    Input("tab-factorlab-btn",    "n_clicks"),
    Input("screener-click-ticker","data"),
    Input("url",                  "pathname"),
    prevent_initial_call=False
)
def switch_tabs(n_screener, n_analyze, n_portfolio, n_factorlab, clicked_ticker, pathname):
    triggered = dash.ctx.triggered_id
    SHOW, HIDE = {"display": "block"}, {"display": "none"}
    ACTIVE, IDLE = "topbar-nav-btn tab-btn active", "topbar-nav-btn tab-btn"
    if triggered == "screener-click-ticker" and clicked_ticker:
        return HIDE, SHOW, HIDE, HIDE, IDLE, ACTIVE, IDLE, IDLE
    if triggered in ("url", None) and (pathname or "").startswith("/analyze/"):
        return HIDE, SHOW, HIDE, HIDE, IDLE, ACTIVE, IDLE, IDLE
    if triggered == "tab-analyze-btn":
        return HIDE, SHOW, HIDE, HIDE, IDLE, ACTIVE, IDLE, IDLE
    if triggered == "tab-portfolio-btn":
        return HIDE, HIDE, SHOW, HIDE, IDLE, IDLE, ACTIVE, IDLE
    if triggered == "tab-factorlab-btn":
        return HIDE, HIDE, HIDE, SHOW, IDLE, IDLE, IDLE, ACTIVE
    return SHOW, HIDE, HIDE, HIDE, ACTIVE, IDLE, IDLE, IDLE


# ── Theme Toggle ────────────────────────────────────────────────────────────
def _make_theme_js(target_theme):
    return f"""
    function(n) {{
        if (!n) return "";
        localStorage.setItem("fr-theme", "{target_theme}");
        if ("{target_theme}" === "light") {{
            document.body.classList.add("light");
        }} else if ("{target_theme}" === "dark") {{
            document.body.classList.remove("light");
        }} else {{
            var prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
            document.body.classList.toggle("light", prefersLight);
        }}
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
        if (theme === "light") {
            document.body.classList.add("light");
        } else if (theme === "dark") {
            document.body.classList.remove("light");
        } else {
            var prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
            document.body.classList.toggle("light", prefersLight);
        }
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
