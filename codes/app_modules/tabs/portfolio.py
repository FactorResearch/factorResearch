"""Portfolio tab callbacks and rendering helpers."""

import dash
from dash import Input, Output, State, callback, dcc, html
import plotly.graph_objects as go

import codes.portfolio as portfolio_engine
from codes import security
from codes.data import db
from codes.app_modules.analysis_ui import _chart_layout
from codes.app_modules.config import (
    AMBER, BLUE, BORDER, DARK, GREEN, MUTED, RED, TEXT,
    validate_portfolio_name,
)
from codes.app_modules.session import get_user_id, invalidate_portfolio_cache
from codes.app_modules.rate_limit import RateLimited, check_rate_limit
from codes.services import permissions
from codes.services import product_analytics
from codes.app_modules.components.feature_lock_modal import FeatureLockedModal
from codes.app_modules.tabs.pricing import open_upgrade_funnel
from codes.app_modules.css_classes import tone_class

PORTFOLIO_SIMULATION_CALLS = 3
PORTFOLIO_SIMULATION_PERIOD_SECONDS = 3600

# ══════════════════════════════════════════════════════════════════════════════
# Portfolio callbacks
# ══════════════════════════════════════════════════════════════════════════════
# ── Populate portfolio dropdowns ──────────────────────────────────────────────
@callback(
    Output("portfolio-select-dropdown", "options"),
    Output("portfolio-active-dropdown", "options"),
    Output("portfolio-compare-dropdown","options"),
    Input("portfolio-refresh-store", "data"),
    prevent_initial_call=False
)
def refresh_portfolio_dropdowns(refresh):
    names = portfolio_engine.list_portfolios(get_user_id())
    opts  = [{"label": n, "value": n} for n in names]
    return opts, opts, opts

# ── Show/hide new-portfolio creation panel ────────────────────────────────────
@callback(
    Output("portfolio-create-panel", "style"),
    Input("portfolio-new-btn",            "n_clicks"),
    Input("portfolio-create-confirm-btn", "n_clicks"),
    Input("portfolio-create-cancel-btn",  "n_clicks"),
    prevent_initial_call=True
)
def toggle_create_panel(new, confirm, cancel):
    triggered = dash.ctx.triggered_id
    if triggered == "portfolio-new-btn":
        return {"display": "block"}
    return {"display": "none"}

# ── Create portfolio ──────────────────────────────────────────────────────────
@callback(
    Output("portfolio-refresh-store",    "data", allow_duplicate=True),
    Output("portfolio-active-dropdown",  "value"),
    Output("portfolio-create-msg",       "children"),
    Output("portfolio-create-name",      "value"),
    Input("portfolio-create-confirm-btn","n_clicks"),
    State("portfolio-create-name",       "value"),
    State("portfolio-refresh-store",     "data"),
    prevent_initial_call=True
)
def create_portfolio(n, name, refresh):
    if not n:
        return dash.no_update, dash.no_update, "", ""
    name = validate_portfolio_name(name)
    if not name:
        return dash.no_update, dash.no_update, "❌ Invalid name (letters, numbers, spaces, - or _, max 32 chars).", dash.no_update
    uid = get_user_id()
    existing = portfolio_engine.list_portfolios(uid)
    if name in existing:
        return dash.no_update, dash.no_update, f"❌ '{name}' already exists.", dash.no_update
    portfolio_engine.create_portfolio(uid, name)
    product_analytics.track_event(uid, "portfolio_created", {"portfolio_name": name})
    security.audit_log_access("CREATE", f"portfolio:{name}", uid)
    return (refresh or 0) + 1, name, "", ""

# ── Delete portfolio ──────────────────────────────────────────────────────────
@callback(
    Output("portfolio-refresh-store",   "data", allow_duplicate=True),
    Output("portfolio-active-dropdown", "value", allow_duplicate=True),
    Output("portfolio-msg",             "children", allow_duplicate=True),
    Input("portfolio-delete-btn",       "n_clicks"),
    State("portfolio-active-dropdown",  "value"),
    State("portfolio-refresh-store",    "data"),
    prevent_initial_call=True
)
def delete_portfolio(n, active, refresh):
    if not n or not active:
        return dash.no_update, dash.no_update, dash.no_update
    portfolio_engine.delete_portfolio(get_user_id(), active)
    invalidate_portfolio_cache()
    security.audit_log_access("DELETE", f"portfolio:{active}", get_user_id())
    return (refresh or 0) + 1, None, f"🗑 Portfolio '{active}' deleted."

# ── Add holding from Analyze tab ──────────────────────────────────────────────
@callback(
    Output("portfolio-add-msg",       "children"),
    Output("portfolio-add-msg",       "style"),
    Output("portfolio-refresh-store", "data", allow_duplicate=True),
    Output("portfolio-shares-input",  "value"),
    Input("portfolio-add-btn",        "n_clicks"),
    State("portfolio-select-dropdown","value"),
    State("portfolio-new-name",       "value"),
    State("portfolio-shares-input",   "value"),
    State("active-analysis-symbol",   "data"),
    State("analysis-store",           "data"),
    State("portfolio-refresh-store",  "data"),
    prevent_initial_call=True
)
def add_to_portfolio(n, selected, new_name, shares, symbol, analysis, refresh):
    if not n:
        return "", {}, dash.no_update, dash.no_update
    # Resolve portfolio name
    port_name = validate_portfolio_name(new_name) or selected
    if not port_name:
        return "❌ Select or name a portfolio first.", {"color": RED}, dash.no_update, dash.no_update
    # Shares validation
    try:
        shares = int(shares or 0)
    except (ValueError, TypeError):
        shares = 0
    if shares < 5:
        return "❌ Minimum 5 shares.", {"color": RED}, dash.no_update, dash.no_update
    if shares > 1000000:
        return "❌ Maximum 1,000,000 shares allowed.", {"color": RED}, dash.no_update, dash.no_update
    if not symbol:
        return "❌ Analyze a stock first.", {"color": RED}, dash.no_update, dash.no_update
    # Create portfolio if it doesn't exist
    uid = get_user_id()
    if port_name not in portfolio_engine.list_portfolios(uid):
        portfolio_engine.create_portfolio(uid,port_name)
    price       = (analysis or {}).get("price") or 0
    company     = (analysis or {}).get("name", symbol)
    _, err = portfolio_engine.add_holding(uid,port_name, symbol, shares, price, company)
    if err:
        return f"❌ {err}", {"color": RED}, dash.no_update, dash.no_update
    product_analytics.track_event(uid, "portfolio_updated", {"portfolio_name": port_name, "symbol": symbol, "action": "add_holding"})
    portfolio_engine.invalidate_simulation_cache(uid, port_name)
    invalidate_portfolio_cache()
    p = portfolio_engine.load_portfolio(uid, port_name)
    count = len(p["holdings"])
    msg = f"✅ Added {shares}× {symbol} to '{port_name}' ({count}/{portfolio_engine.MAX_HOLDINGS} stocks)"
    return msg, {"color": GREEN}, (refresh or 0) + 1, None

# ── Render active portfolio holdings ─────────────────────────────────────────
@callback(
    Output("portfolio-content", "children"),
    Input("portfolio-active-dropdown", "value"),
    Input("portfolio-refresh-store",   "data"),
    prevent_initial_call=False
)
def render_portfolio_holdings(active, refresh):
    if not active:
        return html.Div([
            html.Div("📂", className="portfolio-empty-icon"),
            html.H3("No portfolio selected"),
            html.P("Select or create a portfolio to get started.",
                    className="text-muted"),
        ], className="portfolio-empty")
    p = portfolio_engine.load_portfolio(get_user_id(), active)
    if p is None:
        return html.Div("Portfolio not found.", className="text-danger")
    holdings = p.get("holdings", {})
    count    = len(holdings)
    cap      = portfolio_engine.MAX_HOLDINGS
    header = html.Div(className="portfolio-header", children=[
        html.Div(className="portfolio-header-left", children=[
            html.H2(active),
            html.Span(f"{count}/{cap} stocks",
                      className="fs-13 clr-dim ml-8"),
        ]),
    ])
    if not holdings:
        body = html.Div([
            html.Div("📭", className="portfolio-empty-icon"),
            html.H3("No holdings yet"),
            html.P("Analyze a stock and click 'Add to Portfolio'."),
        ], className="portfolio-empty")
    else:
        total_invested = sum(h["shares"] * h["price_at_add"] for h in holdings.values())
        total_value = sum(
            h["shares"] * (h.get("current_price") or h["price_at_add"])
            for h in holdings.values()
        )
        # ── Summary cards ──
        avg_score = 0
        scored = 0
        for sym, h in holdings.items():
            ca = db.get_analysis(sym)
            if ca and ca.get("composite_score"):
                avg_score += ca["composite_score"]
                scored += 1
        avg_score = avg_score / scored if scored else 0
        summary_cards = html.Div(className="portfolio-summary", children=[
            html.Div(className="portfolio-summary-card", children=[
                html.Div(f"${total_value:,.0f}", className="portfolio-summary-value"),
                html.Div("Total Value", className="portfolio-summary-label"),
            ]),
            html.Div(className="portfolio-summary-card", children=[
                html.Div(f"${total_invested:,.0f}", className="portfolio-summary-value"),
                html.Div("Invested", className="portfolio-summary-label"),
            ]),
            html.Div(className="portfolio-summary-card", children=[
                html.Div(f"{avg_score:.1f}", className="portfolio-summary-value " + (
                    "clr-green" if avg_score >= 50 else "clr-amber" if avg_score >= 35 else "clr-red"
                )),
                html.Div("Avg Score", className="portfolio-summary-label"),
            ]),
            html.Div(className="portfolio-summary-card", children=[
                html.Div(f"{count}", className="portfolio-summary-value"),
                html.Div("Holdings", className="portfolio-summary-label"),
            ]),
        ])
        # ── Holdings table ──
        rows = []
        for sym, h in holdings.items():
            invested = h["shares"] * h["price_at_add"]
            weight   = invested / total_invested * 100 if total_invested > 0 else 0
            current_price = h.get("current_price") or h["price_at_add"]
            current_value = h["shares"] * current_price
            gain_pct = (current_price - h["price_at_add"]) / h["price_at_add"] * 100 if h["price_at_add"] else 0
            gain_class = "pos" if gain_pct >= 0 else "neg"

            sharpe_val = None
            cached_analysis = db.get_analysis(sym)
            if cached_analysis:
                sharpe_val = (cached_analysis.get("risk") or {}).get("sharpe")
            sharpe_str = f"{sharpe_val:.2f}" if sharpe_val is not None else "—"
            sharpe_color = GREEN if (sharpe_val is not None and sharpe_val >= 1.0) else (
                AMBER if (sharpe_val is not None and sharpe_val >= 0) else RED
                if sharpe_val is not None else MUTED
            )
            sharpe_class = (
                "clr-green" if sharpe_val is not None and sharpe_val >= 1.0 else
                "clr-amber" if sharpe_val is not None and sharpe_val >= 0 else
                "clr-red" if sharpe_val is not None else
                "clr-muted"
            )

            rows.append(html.Tr([
                html.Td(sym, className="pcol-symbol"),
                html.Td(
                    html.Div(className="flex align-items-center gap-sm", children=[
                        dcc.Input(
                            id={"type": "shares-edit-input", "index": f"{active}|{sym}"},
                            type="number",
                            value=h["shares"],
                            min=5,
                            step=1,
                            debounce=False,
                            className="shares-input",
                        ),
                        html.Button(
                            "✓",
                            id={"type": "shares-save-btn", "index": f"{active}|{sym}"},
                            n_clicks=0,
                            className="shares-save-btn",
                        ),
                    ])
                ),
                html.Td(f"${h['price_at_add']:.2f}" if h["price_at_add"] else "N/A",
                        className="pcol-num"),
                html.Td(f"${current_value:,.0f}", className="pcol-num"),
                html.Td(f"{weight:.1f}%", className="pcol-num"),
                html.Td(sharpe_str, className=f"pcol-score pcol-num {sharpe_class}",
                        title="Sharpe Ratio from last full analysis. ≥1.0 = good."),
                html.Td(f"{gain_pct:+.1f}%", className=f"pcol-return {gain_class}"),
                html.Td(
                    html.Button("✕", n_clicks=0,
                                id={"type": "remove-holding-btn", "index": f"{active}|{sym}"},
                                className="portfolio-remove-btn")
                ),
            ]))
        table = html.Div(className="portfolio-table-wrap", children=[
            html.Table(className="portfolio-table", children=[
                html.Thead(html.Tr([
                    html.Th("Symbol"), html.Th("Shares"), html.Th("Price"),
                    html.Th("Value"), html.Th("Weight"), html.Th("Sharpe"),
                    html.Th("Return"), html.Th(""),
                ])),
                html.Tbody(rows),
            ]),
        ])
        # ── Action buttons ──
        ready = count >= 10
        actions = html.Div(className="portfolio-actions mt-16 d-flex gap-8", children=[
            html.Button(
                "🚀 Run Simulation" + (f" ({count}/10)" if not ready else ""),
                id="run-simulation-btn",
                className="portfolio-action-btn primary",
                n_clicks=0,
                disabled=(count == 0),
            ),
            html.Button(
                "Optimize",
                id="optimize-portfolio-btn",
                className="portfolio-action-btn",
                n_clicks=0,
                disabled=(count == 0),
            ),
        ])
        body = html.Div([summary_cards, table, actions])
    return html.Div([header, body])

# ── Remove holding ────────────────────────────────────────────────────────────
@callback(
    Output("portfolio-refresh-store", "data", allow_duplicate=True),
    Input({"type": "remove-holding-btn", "index": dash.ALL}, "n_clicks"),
    State("portfolio-refresh-store", "data"),
    prevent_initial_call=True
)
def remove_holding(n_clicks_list, refresh):
    triggered = dash.ctx.triggered_id
    if not triggered or not any(n for n in n_clicks_list if n):
        return dash.no_update
    port_name, symbol = triggered["index"].split("|", 1)
    uid = get_user_id()
    portfolio_engine.remove_holding(uid, port_name, symbol)
    portfolio_engine.invalidate_simulation_cache(uid, port_name)
    invalidate_portfolio_cache()
    return (refresh or 0) + 1

# ── Update shares ─────────────────────────────────────────────────────────────
@callback(
    Output("portfolio-refresh-store", "data", allow_duplicate=True),
    Output("portfolio-msg",           "children", allow_duplicate=True),
    Input({"type": "shares-save-btn", "index": dash.ALL}, "n_clicks"),
    State({"type": "shares-edit-input", "index": dash.ALL}, "value"),
    State({"type": "shares-edit-input", "index": dash.ALL}, "id"),
    State("portfolio-refresh-store", "data"),
    prevent_initial_call=True
)
def update_shares(n_clicks_list, values, ids, refresh):
    triggered = dash.ctx.triggered_id
    if not triggered or not any(n for n in n_clicks_list if n):
        return dash.no_update, dash.no_update
    triggered_index = triggered["index"]
    new_shares = None
    for id_dict, val in zip(ids, values):
        if id_dict["index"] == triggered_index:
            new_shares = val
            break
    if new_shares is None:
        return dash.no_update, "❌ Could not read share count."
    try:
        new_shares = int(new_shares)
    except (ValueError, TypeError):
        return dash.no_update, "❌ Shares must be a whole number."
    if new_shares < portfolio_engine.MIN_SHARES:
        return dash.no_update, f"❌ Minimum {portfolio_engine.MIN_SHARES} shares."
    port_name, symbol = triggered_index.split("|", 1)
    uid = get_user_id()
    p = portfolio_engine.load_portfolio(uid, port_name)
    if p is None:
        return dash.no_update, f"❌ Portfolio '{port_name}' not found."
    if symbol not in p["holdings"]:
        return dash.no_update, f"❌ {symbol} not in portfolio."
    old_shares = p["holdings"][symbol]["shares"]
    if new_shares == old_shares:
        return dash.no_update, f"ℹ️ {symbol} shares unchanged ({old_shares})."
    p["holdings"][symbol]["shares"] = new_shares
    portfolio_engine.save_portfolio(uid, p)
    portfolio_engine.invalidate_simulation_cache(uid, port_name)
    return (refresh or 0) + 1, f"✅ {symbol} updated to {new_shares} shares."

# ── Side-by-side portfolio comparison helpers ─────────────────────────────────
def _two_col(left, right) -> html.Div:
    """Responsive 2-column flex row; stacks on narrow/mobile viewports."""
    return html.Div(
        className="d-flex gap-16 flex-wrap ai-start",
        children=[
            html.Div(left, className="portfolio-two-col"),
            html.Div(right, className="portfolio-two-col"),
        ],
    )


def _comparison_stats_row(port_name: str, bt: dict) -> html.Div:
    """Single-portfolio summary stats row (reused for side-by-side display)."""
    if bt.get("error"):
        return html.Div(f"❌ {bt['error']}", className="text-danger")

    def _delta(val, ref):
        d = val - ref
        sign = "+" if d >= 0 else ""
        delta_class = "clr-green fs-12" if d >= 0 else "clr-red fs-12"
        return html.Span(f" ({sign}${d:,.0f})", className=delta_class)

    return html.Div(className="portfolio-stats-row", children=[
        html.Div(className="stat-item", children=[
            html.Div("Invested", className="stat-label"),
            html.Div(f"${bt['total_invested']:,.2f}", className="stat-value"),
        ]),
        html.Div(className="stat-item", children=[
            html.Div("Portfolio Value", className="stat-label"),
            html.Div([
                html.Span(f"${bt['final_value']:,.2f}", className="stat-value"),
                _delta(bt["final_value"], bt["total_invested"]),
            ]),
        ]),
        html.Div(className="stat-item", children=[
            html.Div("SPY (same $)", className="stat-label"),
            html.Div([
                html.Span(f"${bt['final_spy']:,.2f}", className="stat-value"),
                _delta(bt["final_spy"], bt["spy_invested"]),
            ]),
        ]),
        html.Div(className="stat-item", children=[
            html.Div("Portfolio CAGR", className="stat-label"),
            html.Div(f"{bt['cagr']:+.1f}%", className="stat-value "
                     + ("clr-green" if bt["cagr"] > 0 else "clr-red")),
        ]),
        html.Div(className="stat-item", children=[
            html.Div("SPY CAGR", className="stat-label"),
            html.Div(f"{bt['spy_cagr']:+.1f}%", className="stat-value "
                     + ("clr-green" if bt["spy_cagr"] > 0 else "clr-red")),
        ]),
        html.Div(className="stat-item", children=[
            html.Div("vs SPY", className="stat-label"),
            html.Div(f"{bt['cagr'] - bt['spy_cagr']:+.1f}% / yr", className="stat-value "
                     + ("clr-green" if bt["cagr"] > bt["spy_cagr"] else "clr-red")),
        ]),
    ])


def _comparison_holdings_table(bt: dict) -> html.Div:
    """Holdings detail table (reused for side-by-side display)."""
    if bt.get("error") or not bt.get("holdings_detail"):
        return html.Div()
    detail_rows = []
    for sym, d in bt["holdings_detail"].items():
        gain_color = GREEN if d["gain_pct"] >= 0 else RED
        factor = d.get("split_factor", 1.0)
        orig   = d.get("original_shares", d["shares"])
        if factor and factor != 1.0 and orig:
            split_label = f"÷{1/factor:.0f}" if factor < 1 else f"×{factor:.4g}"
            shares_cell = html.Td([
                str(d["shares"]),
                html.Span(
                    f" (split {split_label})",
                    className="fs-11 clr-amber ml-4"
                ),
            ])
        else:
            shares_cell = html.Td(str(d["shares"]))
        detail_rows.append(html.Tr([
            html.Td(sym, className="font-semibold text-info"),
            shares_cell,
            html.Td(f"${d['entry_price']:.2f}"),
            html.Td(f"${d['current_price']:.2f}"),
            html.Td(f"${d['current_value']:,.2f}"),
            html.Td(f"{d['gain_pct']:+.1f}%",
                    className="clr-green" if d["gain_pct"] >= 0 else "clr-red"),
        ]))
    return html.Div(className="scorecard", children=[
        html.Div("Holdings Performance (10yr backtest period)", className="scorecard-header"),
        html.Table(className="screener-table", children=[
            html.Thead(html.Tr([
                html.Th("Ticker"), html.Th("Shares"),
                html.Th("Entry Price"), html.Th("Exit Price"),
                html.Th("Value"), html.Th("Total Return"),
            ])),
            html.Tbody(detail_rows),
        ]),
    ])


def _comparison_weak_link_card(user_id: str, port_name: str, bt: dict) -> html.Div:
    """Weak-link analysis card (reused for side-by-side display)."""
    if bt.get("error"):
        return html.Div()
    p_obj = portfolio_engine.load_portfolio(user_id, port_name)
    if not p_obj:
        return html.Div()
    wl = portfolio_engine.analyze_weak_links(p_obj, bt)
    if wl.get("error"):
        return html.Div(
            f"⚠️  Weak-link analysis unavailable: {wl['error']}",
            className="clr-muted fs-13 py-8 px-4"
        )
    gap      = wl["gap_cagr"]
    gap_col  = GREEN if gap >= 0 else RED
    gap_text = (
        f"Portfolio CAGR {wl['port_cagr']:+.1f}%  vs  "
        f"SPY {wl['spy_cagr']:+.1f}%  —  {gap:+.2f}% / yr gap "
        f"over {wl['n_years']:.1f} yr"
    )
    if wl.get("weakest"):
        ws  = wl["weakest"]
        wd  = wl["holdings"][ws]
        banner = html.Div(
            f"⚠️  Weakest link: {ws} — "
            f"replacing it with SPY would have improved total returns "
            f"by +{wd['swap_delta_pct']:.2f}%",
            className="portfolio-weak-link-alert portfolio-weak-link-alert--danger br-6 px-14 py-8 mb-12 fs-13 fw-600"
        )
    else:
        banner = html.Div(
            "✅  No weak links — every holding beat SPY over the backtest period.",
            className="portfolio-weak-link-alert portfolio-weak-link-alert--safe br-6 px-14 py-8 mb-12 fs-13 fw-600"
        )
    wl_rows = []
    for sym in wl["ranking"]:
        d       = wl["holdings"][sym]
        verdict = d["verdict"]
        v_col   = (RED   if verdict == "weak link"   else
                   GREEN if verdict == "contributor" else MUTED)
        v_icon  = ("⚠️"  if verdict == "weak link"   else
                   "✅" if verdict == "contributor" else "—")
        wl_rows.append(html.Tr([
            html.Td(sym, className="font-semibold text-info"),
            html.Td(f"{d['weight']:.1f}%"),
            html.Td(f"{d['stock_cagr']:+.1f}%",
                    className="clr-green" if d["stock_cagr"] >= 0 else "clr-red"),
            html.Td(f"{d['cagr_vs_spy']:+.1f}%",
                    className="clr-green" if d["cagr_vs_spy"] >= 0 else "clr-red"),
            html.Td(f"{d['drag_bps']:+.1f}",
                    className="clr-green" if d["drag_bps"] >= 0 else "clr-red"),
            html.Td(f"{d['swap_delta_pct']:+.2f}%",
                    className="clr-green" if d["swap_delta_pct"] <= 0 else "clr-red"),
            html.Td(f"{v_icon} {verdict}",
                    className=(
                        "clr-red fw-600" if verdict == "weak link" else
                        "clr-green fw-600" if verdict == "contributor" else
                        "clr-muted fw-600"
                    )),
        ]))
    return html.Div(className="scorecard", children=[
        html.Div("🔍 Weak Link Analysis", className="scorecard-header"),
        html.Div(gap_text, className=f"fs-13 mb-14 px-4 {tone_class(gap_col)}"),
        banner,
        html.Table(className="screener-table", children=[
            html.Thead(html.Tr([
                html.Th("Ticker"), html.Th("Weight"), html.Th("Stock CAGR"),
                html.Th("vs SPY"), html.Th("Drag (bps)"), html.Th("Swap Δ"),
                html.Th("Verdict"),
            ])),
            html.Tbody(wl_rows),
        ]),
        html.Div(
            "Table sorted worst-to-best.  "
            "Drag (bps): weighted annualised underperformance vs SPY (negative = drag).  "
            "Swap Δ: total-return change if this stock were replaced with SPY "
            "(positive = stock was a drag; negative = stock beat SPY).",
            className="analysis-copy-leading fs-11 clr-muted mt-10 px-4",
        ),
    ])


def _build_comparison_view(user_id: str, active: str, compare: str, cmp_result: dict, palette: list) -> list:
    """
    Side-by-side comparison view: winner banner + 2-column layout for
    stats, combined backtest/Monte Carlo charts, holdings, and weak-link
    analysis. Reuses run_simulation()/analyze_weak_links() results from
    compare_portfolios() — no simulation logic is re-implemented.
    """
    sections = []

    # ── Winner banner ────────────────────────────────────────────────────
    winner  = cmp_result.get("winner")
    score_a = cmp_result.get("score_a", 0)
    score_b = cmp_result.get("score_b", 0)
    reasons = cmp_result.get("reasons", [])
    if winner:
        title, title_color = f"🏆 {winner} is stronger", GREEN
    else:
        title, title_color = "Both portfolios perform similarly.", MUTED
    sections.append(html.Div(className=f"scorecard mt-24 portfolio-comparison-summary {tone_class(title_color)}", children=[
        html.Div(title, className="portfolio-comparison-title fs-15 fw-700"),
        html.Div([
            html.Span(f"{active}: {score_a:.1f}", className="mr-16"),
            html.Span(f"{compare}: {score_b:.1f}"),
        ], className="portfolio-comparison-copy fs-13 clr-muted"),
        html.Ul([
            html.Li(r, className="fs-12 clr-text")
            for r in reasons
        ], className="portfolio-comparison-reasons m-0"),
    ]))

    sim_a = cmp_result["portfolio_a"]
    sim_b = cmp_result["portfolio_b"]
    bt_a, mc_a = sim_a["backtest"], sim_a["montecarlo"]
    bt_b, mc_b = sim_b["backtest"], sim_b["montecarlo"]
    color_a, color_b = palette[0], palette[1]

    # ── Column headers ───────────────────────────────────────────────────
    sections.append(_two_col(
        html.Div(f"📊 {active}", className=f"scorecard-header fs-16 {tone_class(color_a)}"),
        html.Div(f"📊 {compare}", className=f"scorecard-header fs-16 {tone_class(color_b)}"),
    ))

    # ── Side-by-side stats ───────────────────────────────────────────────
    sections.append(_two_col(
        _comparison_stats_row(active, bt_a),
        _comparison_stats_row(compare, bt_b),
    ))

    # ── Combined backtest chart (A + B + single SPY line) ───────────────
    if not bt_a.get("error") and not bt_b.get("error"):
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(
            x=bt_a["dates"], y=bt_a["portfolio_value"],
            name=active, line=dict(color=color_a, width=2.5)
        ))
        fig_bt.add_trace(go.Scatter(
            x=bt_b["dates"], y=bt_b["portfolio_value"],
            name=compare, line=dict(color=color_b, width=2.5)
        ))
        fig_bt.add_trace(go.Scatter(
            x=bt_a["dates"], y=bt_a["spy_value"],
            name="SPY", line=dict(color=MUTED, width=1.5, dash="dot")
        ))
        fig_bt.update_layout(**_chart_layout(
            f"{active} vs {compare} vs SPY — 10yr Backtest (actual $)", many_traces=True
        ))
        fig_bt.update_yaxes(title_text="Portfolio Value ($)", tickprefix="$")
        sections.append(dcc.Graph(figure=fig_bt, config={"displayModeBar": False}))
    elif bt_a.get("error"):
        sections.append(html.Div(f"❌ {active}: {bt_a['error']}", className="text-danger"))
    elif bt_b.get("error"):
        sections.append(html.Div(f"❌ {compare}: {bt_b['error']}", className="text-danger"))

    # ── Combined Monte Carlo chart (A + B medians/bands + single SPY band) ──
    if not mc_a.get("error") and not mc_b.get("error"):
        fig_mc = go.Figure()
        # SPY band (grey) — from portfolio A's projection (same SPY series)
        fig_mc.add_trace(go.Scatter(
            x=mc_a["dates"] + mc_a["dates"][::-1],
            y=mc_a["spy_p90"] + mc_a["spy_p10"][::-1],
            fill="toself", fillcolor="rgba(158,158,158,0.12)",
            line=dict(color="rgba(0,0,0,0)"), name="SPY range", showlegend=True,
        ))
        fig_mc.add_trace(go.Scatter(
            x=mc_a["dates"], y=mc_a["spy_p50"],
            name="SPY median", line=dict(color=MUTED, width=1.5, dash="dot")
        ))
        for mc, name, color in ((mc_a, active, color_a), (mc_b, compare, color_b)):
            r, g_c, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            fill_rgba = f"rgba({r},{g_c},{b},0.12)"
            fig_mc.add_trace(go.Scatter(
                x=mc["dates"] + mc["dates"][::-1],
                y=mc["p90"] + mc["p10"][::-1],
                fill="toself", fillcolor=fill_rgba,
                line=dict(color="rgba(0,0,0,0)"), name=f"{name} range",
            ))
            fig_mc.add_trace(go.Scatter(
                x=mc["dates"], y=mc["p50"],
                name=f"{name} median", line=dict(color=color, width=2.5)
            ))
        fig_mc.update_layout(**_chart_layout(
            f"{active} vs {compare} vs SPY — 2yr Monte Carlo Projection (1,000 paths)",
            many_traces=True
        ))
        fig_mc.update_yaxes(title_text="Projected Value ($)", tickprefix="$")
        sections.append(dcc.Graph(figure=fig_mc, config={"displayModeBar": False}))

    # ── Side-by-side holdings tables ─────────────────────────────────────
    sections.append(_two_col(
        _comparison_holdings_table(bt_a),
        _comparison_holdings_table(bt_b),
    ))

    # ── Side-by-side weak-link analysis ──────────────────────────────────
    sections.append(_two_col(
        _comparison_weak_link_card(user_id, active, bt_a),
        _comparison_weak_link_card(user_id, compare, bt_b),
    ))

    return sections


def _format_pct(value) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.1f}%"


def _optimizer_method_label(key: str) -> str:
    labels = {
        "current": "Current",
        "mean_variance": "Mean-Variance",
        "max_sharpe": "Maximum Sharpe",
        "min_variance": "Minimum Variance",
        "risk_parity": "Risk Parity",
    }
    return labels.get(key, key.replace("_", " ").title())


def _build_optimization_view(result: dict) -> list:
    if result.get("error"):
        return [html.Div(f"❌ {result['error']}", className="text-danger")]

    methods = result.get("methods", {})
    symbols = result.get("symbols", [])
    method_order = ["current", "mean_variance", "max_sharpe", "min_variance", "risk_parity"]

    summary_rows = []
    for key in method_order:
        method = methods.get(key)
        if not method:
            continue
        sharpe = method.get("sharpe")
        sharpe_class = (
            "clr-green" if sharpe is not None and sharpe >= 1.0 else
            "clr-amber" if sharpe is not None and sharpe >= 0 else
            "clr-red" if sharpe is not None else
            "clr-muted"
        )
        summary_rows.append(html.Tr([
            html.Td(_optimizer_method_label(key), className="font-semibold"),
            html.Td(f"{method.get('expected_return', 0):+.2f}%"),
            html.Td(f"{method.get('volatility', 0):.2f}%"),
            html.Td("—" if sharpe is None else f"{sharpe:.3f}", className=sharpe_class),
        ]))

    allocation_rows = []
    for symbol in symbols:
        cells = [html.Td(symbol, className="font-semibold text-info")]
        for key in method_order:
            method = methods.get(key) or {}
            cells.append(html.Td(_format_pct((method.get("weights") or {}).get(symbol))))
        allocation_rows.append(html.Tr(cells))

    sections = [
        html.Div(
            f"Portfolio Optimization — {result.get('portfolio_name', '')}",
            className="scorecard-header mt-24 fs-16",
        ),
        html.Div(className="portfolio-stats-row", children=[
            html.Div(className="stat-item", children=[
                html.Div("Assets", className="stat-label"),
                html.Div(str(len(symbols)), className="stat-value"),
            ]),
            html.Div(className="stat-item", children=[
                html.Div("History", className="stat-label"),
                html.Div(f"{result.get('n_months', 0)} months", className="stat-value"),
            ]),
            html.Div(className="stat-item", children=[
                html.Div("Risk-Free Rate", className="stat-label"),
                html.Div(f"{result.get('risk_free_rate', 0) * 100:.2f}%", className="stat-value"),
            ]),
        ]),
        html.Div(className="scorecard", children=[
            html.Div("Optimizer Metrics", className="scorecard-header"),
            html.Table(className="screener-table", children=[
                html.Thead(html.Tr([
                    html.Th("Method"),
                    html.Th("Expected Return"),
                    html.Th("Volatility"),
                    html.Th("Sharpe"),
                ])),
                html.Tbody(summary_rows),
            ]),
        ]),
        html.Div(className="scorecard", children=[
            html.Div("Suggested Allocation", className="scorecard-header"),
            html.Table(className="screener-table", children=[
                html.Thead(html.Tr([
                    html.Th("Ticker"),
                    html.Th("Current"),
                    html.Th("Mean-Variance"),
                    html.Th("Max Sharpe"),
                    html.Th("Min Variance"),
                    html.Th("Risk Parity"),
                ])),
                html.Tbody(allocation_rows),
            ]),
            html.Div(
                "Advisory output only. Optimized weights do not change portfolio holdings.",
                className="analysis-copy-leading fs-11 clr-muted mt-10 px-4",
            ),
        ]),
    ]
    excluded = result.get("excluded_symbols") or []
    if excluded:
        sections.append(html.Div(
            f"Excluded for insufficient history: {', '.join(excluded)}",
            className="clr-muted fs-12 mt-8 px-4",
        ))
    return sections


# ── Run simulation ────────────────────────────────────────────────────────────
@callback(
    Output("portfolio-sim-results", "children"),
    Output("upgrade-funnel-store", "data", allow_duplicate=True),
    Input("run-simulation-btn",        "n_clicks"),
    State("portfolio-active-dropdown", "value"),
    State("portfolio-compare-dropdown","value"),
    prevent_initial_call=True
)
def run_simulation(n, active, compare):
    if not n or not active:
        return [], None
    uid = get_user_id()
    access = permissions.can_access_feature(uid, permissions.Feature.PORTFOLIO_ANALYTICS)
    if not access.allowed:
        product_analytics.track_event(
            uid,
            "upgrade_viewed",
            {"feature": "portfolio_analytics", "source": "portfolio_sim_lock", "plan": "premium"},
        )
        return FeatureLockedModal(
            feature="portfolio_analytics",
            source="portfolio_sim_lock",
        ), open_upgrade_funnel(
            feature="portfolio_analytics",
            feature_label="Portfolio analytics",
            reason=access.message,
            source="portfolio_sim_lock",
        )
    try:
        check_rate_limit(
            "portfolio_simulation",
            calls=PORTFOLIO_SIMULATION_CALLS,
            period_seconds=PORTFOLIO_SIMULATION_PERIOD_SECONDS,
            key=uid,
        )
    except RateLimited as exc:
        wait = f" Try again in {exc.retry_after} seconds." if exc.retry_after else ""
        product_analytics.track_event(uid, "backtest_failed", {"source": "portfolio", "reason": "rate_limit"})
        return html.Div(f"⏳ Portfolio simulation rate limit reached.{wait}",
                        className="text-danger"), None
    product_analytics.track_event(uid, "backtest_started", {"source": "portfolio", "portfolio_name": active, "compare": compare or ""})

    def _build_sim_charts(port_name: str, color: str) -> list:
        sim = portfolio_engine.run_simulation(uid, port_name)
        if sim.get("error"):
            return [html.Div(f"❌ {sim['error']}", className="text-danger")]
        bt = sim["backtest"]
        mc = sim["montecarlo"]
        components = []
        # ── Summary stats row ──────────────────────────────────────────────
        def _delta(val, ref):
            d = val - ref
            sign = "+" if d >= 0 else ""
            delta_class = "clr-green fs-12" if d >= 0 else "clr-red fs-12"
            return html.Span(f" ({sign}${d:,.0f})", className=delta_class)
        if not bt.get("error"):
            components.append(html.Div(className="portfolio-stats-row", children=[
                html.Div(className="stat-item", children=[
                    html.Div("Invested", className="stat-label"),
                    html.Div(f"${bt['total_invested']:,.2f}", className="stat-value"),
                ]),
                html.Div(className="stat-item", children=[
                    html.Div("Portfolio Value", className="stat-label"),
                    html.Div([
                        html.Span(f"${bt['final_value']:,.2f}", className="stat-value"),
                        _delta(bt["final_value"], bt["total_invested"]),
                    ]),
                ]),
                html.Div(className="stat-item", children=[
                    html.Div("SPY (same $)", className="stat-label"),
                    html.Div([
                        html.Span(f"${bt['final_spy']:,.2f}", className="stat-value"),
                        _delta(bt["final_spy"], bt["spy_invested"]),
                    ]),
                ]),
                html.Div(className="stat-item", children=[
                    html.Div("Portfolio CAGR", className="stat-label"),
                    html.Div(f"{bt['cagr']:+.1f}%", className="stat-value "
                             + ("clr-green" if bt["cagr"] > 0 else "clr-red")),
                ]),
                html.Div(className="stat-item", children=[
                    html.Div("SPY CAGR", className="stat-label"),
                    html.Div(f"{bt['spy_cagr']:+.1f}%", className="stat-value "
                             + ("clr-green" if bt["spy_cagr"] > 0 else "clr-red")),
                ]),
                html.Div(className="stat-item", children=[
                    html.Div("vs SPY", className="stat-label"),
                    html.Div(f"{bt['cagr'] - bt['spy_cagr']:+.1f}% / yr", className="stat-value "
                             + ("clr-green" if bt["cagr"] > bt["spy_cagr"] else "clr-red")),
                ]),
            ]))
        # ── Backtest chart ─────────────────────────────────────────────────
        if not bt.get("error"):
            fig_bt = go.Figure()
            fig_bt.add_trace(go.Scatter(
                x=bt["dates"], y=bt["portfolio_value"],
                name=port_name, line=dict(color=color, width=2.5)
            ))
            fig_bt.add_trace(go.Scatter(
                x=bt["dates"], y=bt["spy_value"],
                name="SPY", line=dict(color=MUTED, width=1.5, dash="dot")
            ))
            fig_bt.update_layout(**_chart_layout(f"{port_name} — 10yr Backtest vs SPY (actual $)", many_traces=True))
            fig_bt.update_yaxes(title_text="Portfolio Value ($)", tickprefix="$")
            components.append(dcc.Graph(figure=fig_bt, config={"displayModeBar": False}))
        # ── Monte Carlo chart ──────────────────────────────────────────────
        if not mc.get("error"):
            fig_mc = go.Figure()
            # SPY band (grey)
            fig_mc.add_trace(go.Scatter(
                x=mc["dates"] + mc["dates"][::-1],
                y=mc["spy_p90"] + mc["spy_p10"][::-1],
                fill="toself", fillcolor="rgba(158,158,158,0.12)",
                line=dict(color="rgba(0,0,0,0)"), name="SPY range", showlegend=True,
            ))
            fig_mc.add_trace(go.Scatter(
                x=mc["dates"], y=mc["spy_p50"],
                name="SPY median", line=dict(color=MUTED, width=1.5, dash="dot")
            ))
            # Portfolio band (colour)
            r, g_c, b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
            fill_rgba = f"rgba({r},{g_c},{b},0.15)"
            fig_mc.add_trace(go.Scatter(
                x=mc["dates"] + mc["dates"][::-1],
                y=mc["p90"] + mc["p10"][::-1],
                fill="toself", fillcolor=fill_rgba,
                line=dict(color="rgba(0,0,0,0)"), name=f"{port_name} range",
            ))
            fig_mc.add_trace(go.Scatter(
                x=mc["dates"], y=mc["p50"],
                name=f"{port_name} median", line=dict(color=color, width=2.5)
            ))
            fig_mc.add_trace(go.Scatter(
                x=mc["dates"], y=mc["p10"],
                name="Worst case (p10)", line=dict(color=color, width=1, dash="dash")
            ))
            fig_mc.add_trace(go.Scatter(
                x=mc["dates"], y=mc["p90"],
                name="Best case (p90)", line=dict(color=color, width=1, dash="dash")
            ))
            fig_mc.update_layout(**_chart_layout(
                f"{port_name} — 2yr Monte Carlo Projection (1,000 paths)", many_traces=True
            ))
            fig_mc.update_yaxes(title_text="Projected Value ($)", tickprefix="$")
            components.append(dcc.Graph(figure=fig_mc, config={"displayModeBar": False}))
        # ── Holdings detail table ──────────────────────────────────────────
        if not bt.get("error") and bt.get("holdings_detail"):
            detail_rows = []
            for sym, d in bt["holdings_detail"].items():
                gain_color = GREEN if d["gain_pct"] >= 0 else RED
                # Build shares cell — show split badge when a forward split occurred
                factor = d.get("split_factor", 1.0)
                orig   = d.get("original_shares", d["shares"])
                if factor and factor != 1.0 and orig:
                    split_label = f"÷{1/factor:.0f}" if factor < 1 else f"×{factor:.4g}"
                    shares_cell = html.Td([
                        str(d["shares"]),
                        html.Span(
                            f" (split {split_label})",
                            className="fs-11 clr-amber ml-4"
                        ),
                    ])
                else:
                    shares_cell = html.Td(str(d["shares"]))
                detail_rows.append(html.Tr([
                    html.Td(sym, className="font-semibold text-info"),
                    shares_cell,
                    html.Td(f"${d['entry_price']:.2f}"),
                    html.Td(f"${d['current_price']:.2f}"),
                    html.Td(f"${d['current_value']:,.2f}"),
                    html.Td(f"{d['gain_pct']:+.1f}%",
                            className="clr-green" if d["gain_pct"] >= 0 else "clr-red"),
                ]))
            components.append(html.Div(className="scorecard", children=[
                html.Div("Holdings Performance (10yr backtest period)", className="scorecard-header"),
                html.Table(className="screener-table", children=[
                    html.Thead(html.Tr([
                        html.Th("Ticker"), html.Th("Shares"),
                        html.Th("Entry Price"), html.Th("Exit Price"),
                        html.Th("Value"), html.Th("Total Return"),
                    ])),
                    html.Tbody(detail_rows),
                ]),
            ]))
        # ── Weak-link analysis ─────────────────────────────────────────────
        if not bt.get("error"):
            p_obj = portfolio_engine.load_portfolio(uid,port_name)
            if p_obj:
                wl = portfolio_engine.analyze_weak_links(p_obj, bt)
                if wl.get("error"):
                    components.append(html.Div(
                        f"⚠️  Weak-link analysis unavailable: {wl['error']}",
                        className="clr-muted fs-13 py-8 px-4"
                    ))
                else:
                    gap      = wl["gap_cagr"]
                    gap_col  = GREEN if gap >= 0 else RED
                    gap_text = (
                        f"Portfolio CAGR {wl['port_cagr']:+.1f}%  vs  "
                        f"SPY {wl['spy_cagr']:+.1f}%  —  {gap:+.2f}% / yr gap "
                        f"over {wl['n_years']:.1f} yr"
                    )
                    # Banner: weakest link callout OR all-clear
                    if wl.get("weakest"):
                        ws  = wl["weakest"]
                        wd  = wl["holdings"][ws]
                        banner = html.Div(
                            f"⚠️  Weakest link: {ws} — "
                            f"replacing it with SPY would have improved total returns "
                            f"by +{wd['swap_delta_pct']:.2f}%",
                            className="portfolio-weak-link-alert portfolio-weak-link-alert--danger br-6 px-14 py-8 mb-12 fs-13 fw-600"
                        )
                    else:
                        banner = html.Div(
                            "✅  No weak links — every holding beat SPY over the backtest period.",
                            className="portfolio-weak-link-alert portfolio-weak-link-alert--safe br-6 px-14 py-8 mb-12 fs-13 fw-600"
                        )
                    # Per-holding rows — worst to best (ranking is worst-first)
                    wl_rows = []
                    for sym in wl["ranking"]:
                        d       = wl["holdings"][sym]
                        verdict = d["verdict"]
                        v_col   = (RED   if verdict == "weak link"   else
                                   GREEN if verdict == "contributor" else MUTED)
                        v_icon  = ("⚠️"  if verdict == "weak link"   else
                                   "✅" if verdict == "contributor" else "—")
                        wl_rows.append(html.Tr([
                            html.Td(sym,
                                    className="font-semibold text-info"),
                            html.Td(f"{d['weight']:.1f}%"),
                            html.Td(f"{d['stock_cagr']:+.1f}%",
                                    className="clr-green" if d["stock_cagr"] >= 0 else "clr-red"),
                            html.Td(f"{d['cagr_vs_spy']:+.1f}%",
                                    className="clr-green" if d["cagr_vs_spy"] >= 0 else "clr-red"),
                            html.Td(f"{d['drag_bps']:+.1f}",
                                    className="clr-green" if d["drag_bps"] >= 0 else "clr-red"),
                            html.Td(f"{d['swap_delta_pct']:+.2f}%",
                                    className="clr-green" if d["swap_delta_pct"] <= 0 else "clr-red"),
                            html.Td(
                                f"{v_icon} {verdict}",
                                className=(
                                    "clr-red fw-600" if verdict == "weak link" else
                                    "clr-green fw-600" if verdict == "contributor" else
                                    "clr-muted fw-600"
                                )
                            ),
                        ]))
                    components.append(html.Div(className="scorecard", children=[
                        html.Div("🔍 Weak Link Analysis", className="scorecard-header"),
                        html.Div(gap_text, className=f"fs-13 mb-14 px-4 {tone_class(gap_col)}"),
                        banner,
                        html.Table(className="screener-table", children=[
                            html.Thead(html.Tr([
                                html.Th("Ticker"),
                                html.Th("Weight"),
                                html.Th("Stock CAGR"),
                                html.Th("vs SPY"),
                                html.Th("Drag (bps)"),
                                html.Th("Swap Δ"),
                                html.Th("Verdict"),
                            ])),
                            html.Tbody(wl_rows),
                        ]),
                        html.Div(
                            "Table sorted worst-to-best.  "
                            "Drag (bps): weighted annualised underperformance vs SPY (negative = drag).  "
                            "Swap Δ: total-return change if this stock were replaced with SPY "
                            "(positive = stock was a drag; negative = stock beat SPY).",
                            className="analysis-copy-leading fs-11 clr-muted mt-10 px-4",
                        ),
                    ]))
        return components
    PALETTE = [BLUE, GREEN, AMBER, "#e040fb", "#00bcd4"]
    if compare and compare != active:
        cmp_result = portfolio_engine.compare_portfolios(uid,active, compare)
        if cmp_result.get("error"):
            return [
                html.Div(f"📊 {active}", className="scorecard-header mt-24 fs-16"),
                *_build_sim_charts(active, PALETTE[0]),
                html.Div(
                    f"⚠️ Comparison unavailable: {cmp_result['error']}",
                    className="clr-muted fs-13 py-8 px-4 mt-16"
                ),
            ], None
        result = _build_comparison_view(uid,active, compare, cmp_result, PALETTE)
        permissions.record_feature_usage(uid, permissions.Feature.PORTFOLIO_ANALYTICS,
                                         usage_key=f"portfolio:{active}:{compare}")
        product_analytics.track_event(uid, "backtest_completed", {"source": "portfolio", "portfolio_name": active, "compare": compare})
        return result, None
    result = [
        html.Div(f"📊 {active}", className="scorecard-header mt-24 fs-16"),
        *_build_sim_charts(active, PALETTE[0]),
    ]
    if not any(getattr(component, "className", None) == "text-danger"
               for component in result):
        permissions.record_feature_usage(uid, permissions.Feature.PORTFOLIO_ANALYTICS,
                                         usage_key=f"portfolio:{active}")
        product_analytics.track_event(uid, "backtest_completed", {"source": "portfolio", "portfolio_name": active})
    return result, None


# ── Optimize portfolio ────────────────────────────────────────────────────────
@callback(
    Output("portfolio-sim-results", "children", allow_duplicate=True),
    Output("upgrade-funnel-store", "data", allow_duplicate=True),
    Input("optimize-portfolio-btn", "n_clicks"),
    State("portfolio-active-dropdown", "value"),
    prevent_initial_call=True,
)
def optimize_portfolio(n, active):
    if not n or not active:
        return [], None
    uid = get_user_id()
    access = permissions.can_access_feature(uid, permissions.Feature.PORTFOLIO_ANALYTICS)
    if not access.allowed:
        product_analytics.track_event(
            uid,
            "upgrade_viewed",
            {"feature": "portfolio_analytics", "source": "portfolio_optimize_lock", "plan": "premium"},
        )
        return FeatureLockedModal(
            feature="portfolio_analytics",
            source="portfolio_optimize_lock",
        ), open_upgrade_funnel(
            feature="portfolio_analytics",
            feature_label="Portfolio analytics",
            reason=access.message,
            source="portfolio_optimize_lock",
        )
    product_analytics.track_event(uid, "portfolio_optimization_started", {"portfolio_name": active})
    result = portfolio_engine.optimize_portfolio(uid, active)
    if result.get("error"):
        product_analytics.track_event(
            uid,
            "portfolio_optimization_failed",
            {"portfolio_name": active, "reason": result["error"]},
        )
    else:
        product_analytics.track_event(uid, "portfolio_optimization_completed", {"portfolio_name": active})
        permissions.record_feature_usage(
            uid,
            permissions.Feature.PORTFOLIO_ANALYTICS,
            usage_key=f"portfolio_optimize:{active}",
        )
    return _build_optimization_view(result), None
