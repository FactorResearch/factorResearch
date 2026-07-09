"""Analyze tab callbacks."""

import re
import time as _time

import dash
from dash import Input, Output, State, callback

from codes.engine import screener
from codes.app_modules.analysis import analyze_stock, _is_rate_limit_error, is_production
from codes.app_modules.analysis_ui import _build_analysis_content
from codes.app_modules.rate_limit import RateLimited, check_rate_limit
from codes.app_modules.session import get_user_id
from codes import billing
from codes.services import permissions

# ── Analyze ───────────────────────────────────────────────────────────────────
# ── New quant UI helpers ──────────────────────────────────────────────────────
@callback(
    Output("url", "pathname"),
    Output("analysis-content",        "children"),
    Output("analysis-store",          "data"),
    Output("status-msg",              "children"),
    Output("analyze-btn",             "disabled"),
    Output("ticker-input",            "disabled"),
    Output("ticker-input",            "value"),
    Output("add-to-portfolio-panel",  "style"),
    Output("active-analysis-symbol",  "data"),
    Output("screener-viewed-store",   "data"),
    Input("analyze-btn",          "n_clicks"),
    Input("screener-click-ticker","data"),
    State("ticker-input",         "value"),
    State("screener-viewed-store","data"),
    prevent_initial_call=True
)
def run_analysis(n_clicks, clicked_ticker, ticker_input_value, viewed_list):
    """
    Single callback: fetch + score + render.
    Because analysis-content is a child of dcc.Loading(id='analysis-loading'),
    Dash shows the spinner for the entire duration of this callback.
    """
    triggered = dash.ctx.triggered_id
    if triggered == "screener-click-ticker" and clicked_ticker:
        ticker = clicked_ticker
    else:
        ticker = ticker_input_value
    if not ticker or not ticker.strip():
        return dash.no_update, [], None, "❌ Please enter a ticker symbol.", False, False, dash.no_update, {"display": "none"}, None, dash.no_update
    symbol = ticker.strip().upper()
    # Input validation: ticker must be 1-6 uppercase letters
    if not re.fullmatch(r"^[A-Z]{1,6}$", symbol):
        return dash.no_update, [], None, "❌ Invalid ticker format. Use 1–6 uppercase letters (A–Z).", False, False, dash.no_update, {"display": "none"}, None, dash.no_update
    # Rate limit (per-user) — max 10 analyze calls per minute
    try:
        check_rate_limit("analyze", calls=10, period_seconds=60)
    except RateLimited as rl:
        return dash.no_update, [], None, f"⏳ Rate limit exceeded — try again in {rl.retry_after}s.", False, False, dash.no_update, {"display": "none"}, None, dash.no_update
    user_id = get_user_id()
    try:
        access = permissions.can_access_feature(user_id, permissions.Feature.ANALYSIS)
        if not access.allowed:
            checkout = billing.get_checkout_url(user_id)
            msg = f"🔒 {access.message} Upgrade: {checkout}"
            return dash.no_update, [], None, msg, False, False, dash.no_update, {"display": "none"}, None, dash.no_update
    except Exception:
        if is_production():
            return dash.no_update, [], None, "🔒 Billing unavailable — please try later.", False, False, dash.no_update, {"display": "none"}, None, dash.no_update
        access = None
    try:
        result = analyze_stock(symbol)
    except Exception as e:
        if _is_rate_limit_error(e):
            message = getattr(e, "user_message", str(e))
            return dash.no_update, [], None, f"❌ {message}", False, False, symbol, {"display": "none"}, None, dash.no_update
        print(f"run_analysis unexpected error: {type(e).__name__}: {e}")
        return dash.no_update, [], None, "❌ Internal server error — please try again later.", False, False, dash.no_update, {"display": "none"}, None, dash.no_update
    if "error" in result:
        return dash.no_update, [], None, f"❌ {result['error']}", False, False, symbol, {"display": "none"}, None, dash.no_update
    viewed_updated = list(set((viewed_list or []) + [symbol]))
    content = _build_analysis_content(result)
    # Update screener row with full analysis data (Graham Number, live price, enhanced score)
    screener.update_stock_after_analysis(symbol, result)
    usage_msg = ""
    if access and access.remaining is not None:
        consumed = permissions.consume_analysis_if_allowed(user_id, ticker=symbol)
        usage_msg = f" · {consumed.remaining} free analyses remaining"
    return (
        f"/analyze/{symbol}/{_time.strftime('%Y%m%d')}",
        content,
        result,
        f"✅ {result['name']} ({symbol}) — Analysis complete{usage_msg}",
        False, False, symbol,
        {"display": "block"},
        symbol,
        viewed_updated,
    )
