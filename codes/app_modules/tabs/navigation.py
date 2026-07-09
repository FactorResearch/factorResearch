"""Top-level tab navigation callbacks."""

import dash
from dash import Input, Output, callback

# ── Tab Navigation ───────────────────────────────────────────────────────────
@callback(
    Output("tab-screener",     "style"),
    Output("tab-analyze",      "style"),
    Output("tab-portfolio",    "style"),
    Output("tab-factorlab",    "style"),
    Output("tab-screener-btn", "className"),
    Output("tab-analyze-btn",  "className"),
    Output("tab-portfolio-btn","className"),
    Output("tab-factorlab-btn","className"),
    Input("tab-screener-btn",     "n_clicks"),
    Input("tab-analyze-btn",      "n_clicks"),
    Input("tab-portfolio-btn",    "n_clicks"),
    Input("tab-factorlab-btn",    "n_clicks"),
    Input("screener-click-ticker","data"),
    prevent_initial_call=False
)
def switch_tabs(n_screener, n_analyze, n_portfolio, n_factorlab, clicked_ticker):
    triggered = dash.ctx.triggered_id
    SHOW, HIDE = {"display": "block"}, {"display": "none"}
    ACTIVE, IDLE = "tab-btn active", "tab-btn"
    if triggered == "screener-click-ticker" and clicked_ticker:
        return HIDE, SHOW, HIDE, HIDE, IDLE, ACTIVE, IDLE, IDLE
    if triggered == "tab-analyze-btn":
        return HIDE, SHOW, HIDE, HIDE, IDLE, ACTIVE, IDLE, IDLE
    if triggered == "tab-portfolio-btn":
        return HIDE, HIDE, SHOW, HIDE, IDLE, IDLE, ACTIVE, IDLE
    if triggered == "tab-factorlab-btn":
        return HIDE, HIDE, HIDE, SHOW, IDLE, IDLE, IDLE, ACTIVE
    # Default: screener
    return SHOW, HIDE, HIDE, HIDE, ACTIVE, IDLE, IDLE, IDLE
