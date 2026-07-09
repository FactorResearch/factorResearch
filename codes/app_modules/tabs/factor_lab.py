"""Factor Lab tab callbacks."""

from dash import Input, Output, State, callback, dcc, html

from codes.app_modules.analysis_ui import _chart_layout
from codes.app_modules.config import AMBER, BLUE, GREEN, MUTED, RED, TEXT
from codes.app_modules.rate_limit import RateLimited, check_rate_limit
from codes.app_modules.session import get_user_id

# ── Factor Lab callbacks ─────────────────────────────────────────────────────

_FB_WEIGHT_KEYS = [
    "graham", "quality", "momentum", "profitability", "fcf_quality",
    "earnings_revision", "capital_allocation", "growth_quality", "risk", "altman"
]


@callback(
    Output("fb-weight-sum-display", "children"),
    Output("fb-weight-sum-display", "style"),
    *[Input(f"fb-w-{k}", "value") for k in _FB_WEIGHT_KEYS],
    prevent_initial_call=False,
)
def update_weight_sum(*values):
    total = sum(v or 0 for v in values)
    if 95 <= total <= 105:
        color, msg = GREEN, f"Weight sum: {total}% ✓ (will normalise to 100%)"
    elif 80 <= total <= 120:
        color, msg = AMBER, f"Weight sum: {total}% — will normalise to 100%"
    else:
        color, msg = RED, f"Weight sum: {total}% — very uneven; will normalise to 100%"
    return msg, {"padding": "8px 18px 14px", "fontSize": "12px",
                 "color": color, "fontStyle": "italic"}


@callback(
    Output("fb-results", "children"),
    Output("fb-status",  "children"),
    Input("fb-run-btn",  "n_clicks"),
    State("fb-top-n",    "value"),
    State("fb-years",    "value"),
    *[State(f"fb-w-{k}", "value") for k in _FB_WEIGHT_KEYS],
    prevent_initial_call=True,
)
def run_factor_backtest_cb(n_clicks, top_n, years, *weight_vals):
    if not n_clicks:
        return [], ""
    try:
        check_rate_limit("backtest", calls=3, period_seconds=60)
    except RateLimited as rl:
        return [html.Div(f"⏳ Backtest rate limited — try again in {rl.retry_after}s.", className="text-danger", style={"padding": "20px"})], "⏳ Rate limited"

    from codes.engine import strategy_cache, user_strategy

    custom_weights = dict(zip(_FB_WEIGHT_KEYS, (v or 0 for v in weight_vals)))

    # Layer 3: persist this user's weight config
    uid = get_user_id()
    user_strategy.set_user_weights(uid, custom_weights)

    # Layer 4: cache-aware backtest, reused across identical configs
    result = strategy_cache.get_or_run_backtest(
        weights=custom_weights,
        top_n=top_n or 10,
        years=years or 5,
    )

    if result.get("error"):
        return [html.Div(f"❌ {result['error']}", className="text-danger",
                         style={"padding": "20px"})], "❌ Error"

    cache_note = " (cached)" if result.get("cache_hit") else ""
    return _render_fb_results(result), (
        f"✅ {result['n_analysed']} stocks scored · "
        f"top {result['top_n']} selected · "
        f"{result['years']}yr backtest{cache_note}"
    )


def _render_fb_results(r: dict) -> list:
    import plotly.graph_objects as go

    bt_c = r["custom"]
    bt_d = r["default"]
    bt_s = r["spy"]

    def _fmt(v, fmt=".1f", suffix="%"):
        return f"{v:{fmt}}{suffix}" if v is not None else "N/A"

    def _cell_color(v, ref):
        if v is None or ref is None:
            return TEXT
        return GREEN if v > ref else RED if v < ref else TEXT

    rows = []
    for label, ck, fmt, sfx in [
        ("CAGR",         "cagr",         ".1f", "%"),
        ("Sharpe Ratio", "sharpe",       ".2f", ""),
        ("Max Drawdown", "max_drawdown", ".1f", "%"),
    ]:
        cv, dv, sv = bt_c.get(ck), bt_d.get(ck), bt_s.get(ck)
        rows.append(html.Tr([
            html.Td(label, style={"color": MUTED, "fontSize": "12px"}),
            html.Td(_fmt(cv, fmt, sfx),
                    style={"color": _cell_color(cv, dv), "fontWeight": "700", "fontSize": "13px"}),
            html.Td(_fmt(dv, fmt, sfx), style={"fontSize": "13px"}),
            html.Td(_fmt(sv, fmt, sfx), style={"fontSize": "13px", "color": MUTED}),
        ]))

    summary = html.Div(className="scorecard", style={"marginTop": "20px"}, children=[
        html.Div("📊 Performance Comparison", className="scorecard-header"),
        html.Div(
            "Green = custom beats default. Equal-weight buy-and-hold on stocks in your analysis cache.",
            style={"fontSize": "12px", "color": MUTED, "padding": "0 18px 10px", "fontStyle": "italic"},
        ),
        html.Table(className="screener-table", children=[
            html.Thead(html.Tr([
                html.Th("Metric"),
                html.Th("Custom Weights", style={"color": BLUE}),
                html.Th("Default Weights"),
                html.Th("SPY", style={"color": MUTED}),
            ])),
            html.Tbody(rows),
        ]),
    ])

    chart = html.Div()
    if not bt_c.get("error") and not bt_d.get("error") and not bt_s.get("error"):
        def _norm(vals):
            if not vals or vals[0] == 0:
                return vals
            base = vals[0]
            return [round(v / base * 100, 2) for v in vals]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=bt_c["dates"], y=_norm(bt_c["values"]),
            name="Custom Weights", line=dict(color=BLUE, width=2.5)
        ))
        fig.add_trace(go.Scatter(
            x=bt_d["dates"], y=_norm(bt_d["values"]),
            name="Default Weights", line=dict(color=GREEN, width=2, dash="dash")
        ))
        fig.add_trace(go.Scatter(
            x=bt_s["dates"], y=_norm(bt_s["values"]),
            name="SPY", line=dict(color=MUTED, width=1.5, dash="dot")
        ))
        fig.update_layout(**_chart_layout(
            f"Custom vs Default vs SPY — {r['years']}yr equal-weight backtest (indexed to 100)",
            many_traces=True,
        ))
        fig.update_yaxes(title_text="Indexed Value (100 = start)")
        chart = dcc.Graph(figure=fig, config={"displayModeBar": False})

    wc_rows = []
    for wc in r.get("weight_changes", []):
        delta = wc["delta"]
        d_color = GREEN if delta > 1 else RED if delta < -1 else MUTED
        wc_rows.append(html.Tr([
            html.Td(wc["factor"].replace("_", " ").title(), style={"fontSize": "12px"}),
            html.Td(f"{wc['custom']:.1f}%",
                    style={"fontWeight": "700", "color": BLUE, "fontSize": "13px"}),
            html.Td(f"{wc['default']:.1f}%", style={"fontSize": "12px", "color": MUTED}),
            html.Td(f"{delta:+.1f}pp",
                    style={"fontWeight": "600", "color": d_color, "fontSize": "12px"}),
        ]))

    weight_table = html.Div(className="scorecard", style={"marginTop": "16px"}, children=[
        html.Div("⚖️ Weight Changes vs Default", className="scorecard-header"),
        html.Table(className="screener-table", children=[
            html.Thead(html.Tr([html.Th("Factor"), html.Th("Custom"), html.Th("Default"), html.Th("Δ pp")])),
            html.Tbody(wc_rows),
        ]),
    ])

    custom_set  = set(r.get("custom_top",  []))
    default_set = set(r.get("default_top", []))

    stock_rows = []
    for s in r.get("ranked_stocks", []):
        sym   = s["symbol"]
        delta = s.get("delta", 0)
        d_color = GREEN if delta > 2 else RED if delta < -2 else MUTED
        stock_rows.append(html.Tr([
            html.Td(sym, className="font-semibold text-info"),
            html.Td(s["name"][:22], style={"fontSize": "11px", "color": MUTED}),
            html.Td(f"{s['custom_score']:.1f}",
                    style={"fontWeight": "700", "color": BLUE}),
            html.Td(f"{s['default_score']:.1f}"),
            html.Td(f"{delta:+.1f}", style={"color": d_color, "fontWeight": "600"}),
            html.Td("✅" if sym in custom_set  else "—", style={"textAlign": "center"}),
            html.Td("✅" if sym in default_set else "—", style={"textAlign": "center"}),
        ]))

    overlap = r.get("overlap", [])
    stocks_table = html.Div(className="scorecard", style={"marginTop": "16px"}, children=[
        html.Div(
            f"🏆 Stock Rankings — Custom top-{r['top_n']}: "
            f"{', '.join(r['custom_top'][:6])}{'...' if len(r['custom_top']) > 6 else ''}",
            className="scorecard-header",
        ),
        html.Div(
            f"Portfolio overlap: {len(overlap)}/{r['top_n']} stocks in both — "
            f"{', '.join(overlap) if overlap else 'none in common'}",
            style={"fontSize": "12px", "color": MUTED, "padding": "4px 18px 10px", "fontStyle": "italic"},
        ),
        html.Table(className="screener-table", children=[
            html.Thead(html.Tr([
                html.Th("Ticker"), html.Th("Name"),
                html.Th("Custom Score", style={"color": BLUE}),
                html.Th("Default Score"),
                html.Th("Δ Score"),
                html.Th("In Custom"),
                html.Th("In Default"),
            ])),
            html.Tbody(stock_rows),
        ]),
    ])

    warns = []
    for label, bt in [("Custom", bt_c), ("Default", bt_d), ("SPY", bt_s)]:
        if bt.get("error"):
            warns.append(html.Div(f"⚠️ {label}: {bt['error']}",
                                  style={"color": AMBER, "fontSize": "12px", "padding": "4px 0"}))

    return [summary, chart, weight_table, stocks_table] + warns
