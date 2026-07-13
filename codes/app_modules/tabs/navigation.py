"""Top-level tab navigation and theme callbacks."""

import dash
from dash import Input, Output, State, callback, clientside_callback

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
    Input("screener-click-ticker","data"),
    Input("upgrade-funnel-store", "data"),
    Input("url",                  "pathname"),
    State("tab-screener-btn",     "n_clicks_timestamp"),
    State("tab-analyze-btn",      "n_clicks_timestamp"),
    State("tab-portfolio-btn",    "n_clicks_timestamp"),
    State("tab-factorlab-btn",    "n_clicks_timestamp"),
    State("tab-pricing-btn",      "n_clicks_timestamp"),
    prevent_initial_call=False
)
def switch_tabs(
    n_screener,
    n_analyze,
    n_portfolio,
    n_factorlab,
    n_pricing,
    clicked_ticker,
    upgrade_context,
    pathname,
    ts_screener=None,
    ts_analyze=None,
    ts_portfolio=None,
    ts_factorlab=None,
    ts_pricing=None,
):
    triggered = dash.ctx.triggered_id
    SHOW, HIDE = {"display": "block"}, {"display": "none"}
    ACTIVE, IDLE = "topbar-nav-btn tab-btn active", "topbar-nav-btn tab-btn"

    def _result(tab: str):
        return (
            SHOW if tab == "screener" else HIDE,
            SHOW if tab == "analyze" else HIDE,
            SHOW if tab == "portfolio" else HIDE,
            SHOW if tab == "factorlab" else HIDE,
            SHOW if tab == "pricing" else HIDE,
            ACTIVE if tab == "screener" else IDLE,
            ACTIVE if tab == "analyze" else IDLE,
            ACTIVE if tab == "portfolio" else IDLE,
            ACTIVE if tab == "factorlab" else IDLE,
            ACTIVE if tab == "pricing" else IDLE,
        )

    def _latest_clicked_tab() -> str | None:
        timestamps = {
            "screener": ts_screener,
            "analyze": ts_analyze,
            "portfolio": ts_portfolio,
            "factorlab": ts_factorlab,
            "pricing": ts_pricing,
        }
        normalized = {}
        for tab, value in timestamps.items():
            try:
                normalized[tab] = int(value or -1)
            except (TypeError, ValueError):
                normalized[tab] = -1
        tab, timestamp = max(normalized.items(), key=lambda item: item[1])
        return tab if timestamp >= 0 else None

    if triggered == "screener-click-ticker" and clicked_ticker:
        return _result("analyze")
    if triggered == "upgrade-funnel-store" and upgrade_context:
        return _result("pricing")
    if triggered == "tab-screener-btn" and n_screener:
        return _result("screener")
    if triggered == "tab-analyze-btn":
        return _result("analyze")
    if triggered == "tab-portfolio-btn":
        return _result("portfolio")
    if triggered == "tab-factorlab-btn":
        return _result("factorlab")
    if triggered == "tab-pricing-btn":
        return _result("pricing")
    if (pathname or "").startswith("/analyze/"):
        return _result("analyze")
    if (pathname or "") == "/pricing":
        return _result("pricing")
    return _result(_latest_clicked_tab() or "screener")


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
