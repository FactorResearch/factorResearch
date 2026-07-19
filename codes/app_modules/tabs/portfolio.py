"""Portfolio tab callbacks and rendering helpers."""

import json
import time as _time
from urllib.parse import quote, unquote

import dash
import plotly.graph_objects as go
from dash import Input, Output, State, callback, clientside_callback, dcc, html
from flask import has_request_context

from codes import security
from codes.app_modules.analysis_ui import _chart_layout
from codes.app_modules.company_identity import company_logo
from codes.app_modules.components.feature_lock_modal import FeatureLockedModal
from codes.app_modules.config import (
    AMBER,
    BLUE,
    GREEN,
    MUTED,
    RED,
    validate_portfolio_name,
)
from codes.app_modules.css_classes import tone_class
from codes.app_modules.design_system.financial import data_trust_panel, delta
from codes.app_modules.design_system.layouts import container, mobile_action_bar
from codes.app_modules.design_system.primitives import (
    button,
    empty_state,
    input_control,
    responsive_table,
    table,
)
from codes.app_modules.design_system.states import background_job_status, section_error
from codes.app_modules.rate_limit import RateLimited, check_rate_limit
from codes.app_modules.session import get_user_id, invalidate_portfolio_cache
from codes.app_modules.tabs.pricing import open_upgrade_funnel
from codes.services import performance_metrics, permissions, product_analytics
from codes.services import portfolio_service as portfolio_engine
from codes.services.adaptive_loading import AsyncStatus, jobs


def _telemetry_user_id() -> str:
    """Avoid making optional telemetry a request-context dependency."""
    return get_user_id() if has_request_context() else "anonymous"


PORTFOLIO_SIMULATION_CALLS = 3
PORTFOLIO_SIMULATION_PERIOD_SECONDS = 3600


def _portfolio_path(name: str | None) -> str:
    """Return the canonical client route for a validated portfolio name."""
    validated = validate_portfolio_name(name or "")
    return f"/portfolio/{quote(validated, safe='')}" if validated else "/portfolio"


def _portfolio_name_from_path(pathname: str | None) -> str | None:
    """Decode a portfolio route without loading or revealing a user-owned record."""
    prefix = "/portfolio/"
    raw_path = str(pathname or "")
    if not raw_path.startswith(prefix):
        return None
    encoded_name = raw_path[len(prefix) :].rstrip("/")
    if not encoded_name or "/" in encoded_name:
        return None
    try:
        return validate_portfolio_name(unquote(encoded_name))
    except (UnicodeDecodeError, ValueError):
        return None


def _analysis_score(analysis: dict | None) -> float | None:
    if not analysis:
        return None
    value = (analysis.get("enhanced") or {}).get("composite_score")
    if value is None:
        value = analysis.get("composite_score")
    if value is None:
        value = (analysis.get("composite") or {}).get("composite_score")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def portfolio_health_snapshot(holdings: dict, analysis_entries: dict) -> dict:
    """Build non-authoritative display insights from holdings and cached research.

    The derived values feed summary metrics and section-local review signals.
    Missing research remains unavailable. A research weak link is returned only
    when at least two holdings have scores and exactly one has the lowest score;
    ties and single-score portfolios do not receive an arbitrary label. This is
    a display-only research comparison, not the historical counterfactual weak
    link calculated by the portfolio simulation engine.

    Args:
        holdings: User-owned holdings keyed by ticker, with shares and available
            current or entry prices.
        analysis_entries: Optional cached analyses keyed by ticker.

    Returns:
        Display-only aggregate score, coverage, concentration, sector, freshness,
        risk observations, and an optional uniquely lowest researched holding.

    Side Effects:
        None. Holdings, persistence, caches, and analysis records are not changed.
    """
    positions = []
    for symbol, holding in holdings.items():
        current_price = holding.get("current_price") or holding.get("price_at_add") or 0
        current_value = (holding.get("shares") or 0) * current_price
        entry = analysis_entries.get(symbol) or {}
        analysis = entry.get("data") or {}
        positions.append(
            {
                "symbol": symbol,
                "value": current_value,
                "score": _analysis_score(analysis),
                "updated_at": entry.get("updated_at") or analysis.get("updated_at"),
                "sector": analysis.get("sector") or "Unknown",
            }
        )
    total_value = sum(position["value"] for position in positions)
    for position in positions:
        position["weight"] = position["value"] / total_value * 100 if total_value else 0

    scored = [position for position in positions if position["score"] is not None]
    avg_score = sum(position["score"] for position in scored) / len(scored) if scored else 0
    coverage = len(scored) / len(positions) * 100 if positions else 0
    largest = max(positions, key=lambda position: position["weight"], default=None)
    weak_link = None
    if len(scored) >= 2:
        lowest_score = min(position["score"] for position in scored)
        lowest_positions = [
            position for position in scored if position["score"] == lowest_score
        ]
        if len(lowest_positions) == 1:
            weak_link = lowest_positions[0]
    if coverage < 60 or avg_score < 45:
        health = "Needs review"
    elif coverage < 100 or avg_score < 65:
        health = "Mixed"
    else:
        health = "Strong"

    risks = []
    if largest and largest["weight"] >= 25:
        risks.append(
            f"{largest['symbol']} is {largest['weight']:.1f}% of current value, creating concentration risk."
        )
    if coverage < 100:
        risks.append(
            f"Research coverage is {coverage:.0f}%; refresh unscored holdings before relying on the aggregate."
        )
    if len(positions) < 10:
        risks.append(
            f"Only {len(positions)} holdings are present, so diversification may be limited."
        )
    if not risks:
        risks.append("No critical concentration or research-coverage warning is active.")

    sectors = {position["sector"] for position in positions if position["sector"] != "Unknown"}
    freshness = max(
        (str(position["updated_at"]) for position in positions if position["updated_at"]),
        default="Unavailable",
    )
    return {
        "health": health,
        "average_score": avg_score,
        "coverage": coverage,
        "largest": largest,
        "weak_link": weak_link,
        "risks": risks,
        "sector_count": len(sectors),
        "freshness": freshness,
    }


def _portfolio_metric(label: str, value: str, detail: str, *, tone: str = "neutral") -> html.Article:
    """Render one mockup-aligned metric using already-calculated portfolio data."""
    return html.Article(
        [html.Span(label), html.Strong(value), html.Small(detail)],
        className=f"portfolio-metric-card portfolio-metric-card--{tone}",
    )


def _portfolio_allocation_card(
    holdings: dict, analyses: dict[str, dict | None], total_value: float
) -> html.Section:
    """Render current-value sector allocation as an accessible donut and legend.

    Unknown sectors remain explicit and zero total value produces a section-local
    empty state. The visible legend duplicates every chart value in text so the
    allocation does not rely on color or Plotly interaction alone.
    """
    sector_values: dict[str, float] = {}
    for symbol, holding in holdings.items():
        analysis = analyses.get(symbol) or {}
        sector = str(analysis.get("sector") or "Unknown")
        price = holding.get("current_price") or holding.get("price_at_add") or 0
        sector_values[sector] = sector_values.get(sector, 0) + (holding.get("shares") or 0) * price
    ordered = sorted(sector_values.items(), key=lambda item: item[1], reverse=True)
    if not ordered or total_value <= 0:
        allocation_body = empty_state(
            "Allocation unavailable",
            "Add holdings with usable prices to calculate sector allocation.",
            icon="Allocation",
        )
    else:
        labels = [sector for sector, _value in ordered]
        values = [value for _sector, value in ordered]
        figure = go.Figure(
            go.Pie(
                labels=labels,
                values=values,
                hole=0.62,
                sort=False,
                direction="clockwise",
                textinfo="none",
                hovertemplate="%{label}: %{percent:.1%}<extra></extra>",
                marker={"colors": [BLUE, GREEN, AMBER, RED, MUTED]},
            )
        )
        figure.update_layout(
            **_chart_layout(""),
            showlegend=False,
            height=250,
            margin={"l": 8, "r": 8, "t": 8, "b": 8},
        )
        allocation_body = html.Div(
            [
                html.Div(
                    dcc.Graph(
                        figure=figure,
                        config={"displayModeBar": False, "responsive": True},
                        className="portfolio-allocation-chart",
                    ),
                    className="portfolio-allocation-visual",
                    role="img",
                    **{"aria-label": "Portfolio sector allocation donut chart"},
                ),
                html.Ul(
                    [
                        html.Li(
                            [
                                html.Span(sector),
                                html.Strong(f"{value / total_value * 100:.1f}%"),
                            ]
                        )
                        for sector, value in ordered
                    ],
                    className="portfolio-allocation-list",
                    **{"aria-label": "Portfolio sector allocation values"},
                ),
            ],
            className="portfolio-allocation-body",
        )
    return html.Section(
        [
            html.Div(
                [html.Div([html.H2("Allocation"), html.P("By sector")])],
                className="portfolio-card-header",
            ),
            allocation_body,
        ],
        className=(
            "portfolio-dashboard-card portfolio-card-span-2 portfolio-allocation-card"
        ),
        **{"aria-label": "Portfolio allocation by sector"},
    )


def _portfolio_weak_link_card(weak_link: dict | None) -> html.Section:
    """Render one uniquely lowest research score without claiming return drag.

    The card is a pre-simulation review priority. Historical performance weak-link
    classification remains owned by ``codes.portfolio.analyze_weak_links``.
    """
    if weak_link:
        symbol = weak_link["symbol"]
        body = [
            company_logo(symbol, symbol, "company-logo portfolio-weak-link-logo"),
            html.Div(
                [
                    html.Strong(symbol),
                    html.P(f"Lowest researched score at {weak_link['score']:.0f}/100."),
                    html.A("Review position", href=f"#portfolio-holding-{symbol}"),
                ]
            ),
        ]
    else:
        body = [
            html.Div(
                [
                    html.Strong("No unique research weak link"),
                    html.P(
                        "At least two differently scored holdings are required for a relative comparison."
                    ),
                ]
            )
        ]
    return html.Section(
        [
            html.Div(
                [html.Div([html.H2("Weak link"), html.P("Lowest relative research score")])],
                className="portfolio-card-header",
            ),
            html.Div(body, className="portfolio-weak-link-body"),
        ],
        className="portfolio-dashboard-card portfolio-weak-link-card",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Portfolio callbacks
# ══════════════════════════════════════════════════════════════════════════════
# ── Populate portfolio dropdowns ──────────────────────────────────────────────
@callback(
    Output("portfolio-select-dropdown", "options"),
    Output("portfolio-active-dropdown", "options"),
    Output("portfolio-compare-dropdown", "options"),
    Output("portfolio-active-dropdown", "value"),
    Input("portfolio-refresh-store", "data"),
    Input("url", "pathname"),
    State("portfolio-active-dropdown", "value"),
    prevent_initial_call=False,
)
def refresh_portfolio_dropdowns(refresh, pathname, current_active):
    """Refresh user-owned options and restore only changed route selections.

    Route-triggered calls authorize and restore a selected name. Data-refresh
    calls update option lists but preserve an already-valid Dash value with
    ``no_update``; re-emitting it would retrigger route synchronization and the
    full portfolio renderer without representing a user-visible state change.
    """
    names = portfolio_engine.list_portfolios(get_user_id())
    opts = [{"label": n, "value": n} for n in names]
    routed_name = _portfolio_name_from_path(pathname)
    triggered = dash.ctx.triggered_id
    if triggered in ("url", None) and str(pathname or "").startswith("/portfolio"):
        selected = routed_name if routed_name in names else None
    elif current_active in names:
        selected = (
            dash.no_update if triggered == "portfolio-refresh-store" else current_active
        )
    else:
        selected = None
    return opts, opts, opts, selected


# Route writes use the browser history API so the declared Dash dependency graph
# remains one-way (URL -> authorized dropdown selection) and cannot form a
# callback cycle. Dispatching popstate updates dcc.Location and global navigation.
clientside_callback(
    """
    function(portfolioClicks, active, pathname) {
        var trigger = window.dash_clientside.callback_context.triggered_id;
        if (trigger !== 'tab-portfolio-btn' && trigger !== 'portfolio-active-dropdown') {
            return window.dash_clientside.no_update;
        }
        var target = active
            ? '/portfolio/' + encodeURIComponent(active)
            : '/portfolio';
        if (pathname !== target) {
            window.history.pushState(window.history.state, '', target);
            window.dispatchEvent(new PopStateEvent('popstate'));
        }
        return target;
    }
    """,
    Output("portfolio-url-state-sink", "children"),
    Input("tab-portfolio-btn", "n_clicks"),
    Input("portfolio-active-dropdown", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)


# ── Show/hide new-portfolio creation panel ────────────────────────────────────
@callback(
    Output("portfolio-create-panel", "style"),
    Input("portfolio-new-btn", "n_clicks"),
    Input("portfolio-create-confirm-btn", "n_clicks"),
    Input("portfolio-create-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_create_panel(new, confirm, cancel):
    triggered = dash.ctx.triggered_id
    if triggered == "portfolio-new-btn":
        return {"display": "block"}
    return {"display": "none"}


# ── Create portfolio ──────────────────────────────────────────────────────────
@callback(
    Output("portfolio-refresh-store", "data", allow_duplicate=True),
    Output("portfolio-active-dropdown", "value", allow_duplicate=True),
    Output("portfolio-create-msg", "children"),
    Output("portfolio-create-name", "value"),
    Input("portfolio-create-confirm-btn", "n_clicks"),
    State("portfolio-create-name", "value"),
    State("portfolio-refresh-store", "data"),
    prevent_initial_call=True,
)
def create_portfolio(n, name, refresh):
    if not n:
        return dash.no_update, dash.no_update, "", ""
    name = validate_portfolio_name(name)
    if not name:
        return (
            dash.no_update,
            dash.no_update,
            "❌ Invalid name (letters, numbers, spaces, - or _, max 32 chars).",
            dash.no_update,
        )
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
    Output("portfolio-refresh-store", "data", allow_duplicate=True),
    Output("portfolio-active-dropdown", "value", allow_duplicate=True),
    Output("portfolio-msg", "children", allow_duplicate=True),
    Input("portfolio-delete-btn", "n_clicks"),
    State("portfolio-active-dropdown", "value"),
    State("portfolio-refresh-store", "data"),
    prevent_initial_call=True,
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
    Output("portfolio-add-msg", "children"),
    Output("portfolio-add-msg", "style"),
    Output("portfolio-refresh-store", "data", allow_duplicate=True),
    Output("portfolio-shares-input", "value"),
    Input("portfolio-add-btn", "n_clicks"),
    State("portfolio-select-dropdown", "value"),
    State("portfolio-new-name", "value"),
    State("portfolio-shares-input", "value"),
    State("active-analysis-symbol", "data"),
    State("analysis-store", "data"),
    State("portfolio-refresh-store", "data"),
    prevent_initial_call=True,
)
def add_to_portfolio(n, selected, new_name, shares, symbol, analysis, refresh):
    if not n:
        return "", {}, dash.no_update, dash.no_update
    # Resolve portfolio name
    port_name = validate_portfolio_name(new_name) or selected
    if not port_name:
        return (
            "❌ Select or name a portfolio first.",
            {"color": RED},
            dash.no_update,
            dash.no_update,
        )
    # Shares validation
    try:
        shares = int(shares or 0)
    except (ValueError, TypeError):
        shares = 0
    if shares < 5:
        return "❌ Minimum 5 shares.", {"color": RED}, dash.no_update, dash.no_update
    if shares > 1000000:
        return (
            "❌ Maximum 1,000,000 shares allowed.",
            {"color": RED},
            dash.no_update,
            dash.no_update,
        )
    if not symbol:
        return "❌ Analyze a stock first.", {"color": RED}, dash.no_update, dash.no_update
    # Create portfolio if it doesn't exist
    uid = get_user_id()
    if port_name not in portfolio_engine.list_portfolios(uid):
        portfolio_engine.create_portfolio(uid, port_name)
    price = (analysis or {}).get("price") or 0
    company = (analysis or {}).get("name", symbol)
    _, err = portfolio_engine.add_holding(uid, port_name, symbol, shares, price, company)
    if err:
        return f"❌ {err}", {"color": RED}, dash.no_update, dash.no_update
    product_analytics.track_event(
        uid,
        "portfolio_updated",
        {"portfolio_name": port_name, "symbol": symbol, "action": "add_holding"},
    )
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
    Input("portfolio-refresh-store", "data"),
    prevent_initial_call=False,
)
def render_portfolio_holdings(active, refresh):
    """Render one authorized portfolio as a single summary-first dashboard.

    The callback reads user-owned holdings plus optional cached analysis data.
    Independent enrichment failure degrades research sections without removing
    holdings controls. Summary metrics have one visual owner; provenance is a
    closed disclosure; Allocation and the research weak link form the first row;
    and editable Holdings occupies the full row beneath them.
    """
    started_at = _time.perf_counter()
    if not active:
        return empty_state(
            "No portfolio selected",
            "Select or create a portfolio to get started.",
            icon="Portfolio",
        )
    p = portfolio_engine.load_portfolio(get_user_id(), active)
    if p is None:
        performance_metrics.record_ui_operation(
            "portfolio-load",
            (_time.perf_counter() - started_at) * 1000,
            outcome="error",
            section="portfolio-holdings",
        )
        return html.Div("Portfolio not found.", className="text-danger")
    holdings = p.get("holdings", {})
    count = len(holdings)
    cap = portfolio_engine.MAX_HOLDINGS
    header = html.Header(
        className="portfolio-page-heading",
        children=[
            html.Div(
                children=[
                    html.P("Portfolio intelligence", className="portfolio-page-eyebrow"),
                    html.H1(active),
                    html.P(
                        f"Risk, return, concentration, and scenario analysis · {count}/{cap} holdings."
                    ),
                ],
            ),
        ],
    )
    if not holdings:
        body = empty_state(
            "No holdings yet",
            "Analyze a stock and choose Add to Portfolio.",
            icon="Holdings",
        )
    else:
        total_invested = sum(h["shares"] * h["price_at_add"] for h in holdings.values())
        total_value = sum(
            h["shares"] * (h.get("current_price") or h["price_at_add"]) for h in holdings.values()
        )
        # ── Summary cards ──
        try:
            analysis_entries = portfolio_engine.analysis_entries(holdings)
        except Exception:
            # Cached enrichment is optional; holdings and user-entered values
            # remain usable when a provider/cache read fails.
            analysis_entries = {}
        analyses = {symbol: (analysis_entries.get(symbol) or {}).get("data") for symbol in holdings}
        currencies = {
            ((analysis or {}).get("provenance") or {}).get("currency")
            or (analysis or {}).get("currency")
            for analysis in analyses.values()
            if analysis
        }
        currencies.discard(None)
        mixed_currency = len(currencies) > 1
        portfolio_trust = data_trust_panel(
            {
                "generated_at": max(
                    (
                        str(
                            (analysis or {}).get("generated_at")
                            or (analysis or {}).get("updated_at")
                        )
                        for analysis in analyses.values()
                        if analysis
                        and (
                            (analysis or {}).get("generated_at")
                            or (analysis or {}).get("updated_at")
                        )
                    ),
                    default=None,
                ),
                "provenance": {
                    "source_category": "Cached company analyses and user-entered holdings",
                    "filing_period": "Varies by holding; inspect each company analysis",
                    "currency": ", ".join(sorted(currencies)) if currencies else "USD presentation",
                    "price_timestamp": (
                        "Exchange-rate timestamp unavailable; mixed-currency totals are indicative"
                        if mixed_currency
                        else "Latest cached holding prices; timestamps vary"
                    ),
                    "normalization_status": "Holding values normalized to the displayed portfolio totals",
                    "calculation_status": "Portfolio aggregate",
                    "model_scope": "Cenvarn default models",
                    "missing_effects": (
                        [
                            "Mixed-currency conversion lacks a stored exchange-rate timestamp; treat aggregate values as indicative."
                        ]
                        if mixed_currency
                        else []
                    ),
                },
            },
            compact=True,
            collapsible=True,
        )
        portfolio_trust.className += " portfolio-data-trust"
        health = portfolio_health_snapshot(holdings, analysis_entries)
        scores = [
            analysis["composite_score"]
            for analysis in analyses.values()
            if analysis and analysis.get("composite_score") is not None
        ]
        avg_score = sum(scores) / len(scores) if scores else None
        weak_link = health["weak_link"]
        largest = health["largest"]
        concentration = largest["weight"] if largest else None
        concentration_tone = "warning" if concentration is not None and concentration >= 25 else "neutral"
        summary_cards = html.Section(
            [
                _portfolio_metric(
                    "Total value",
                    f"${total_value:,.0f}",
                    f"${total_invested:,.0f} invested",
                ),
                _portfolio_metric(
                    "Portfolio score",
                    f"{avg_score:.0f}" if avg_score is not None else "N/A",
                    "Average researched score"
                    if avg_score is not None
                    else "Research unavailable",
                    tone="positive" if avg_score is not None and avg_score >= 65 else "neutral",
                ),
                _portfolio_metric(
                    "Research coverage",
                    f"{health['coverage']:.0f}%",
                    f"{len(scores)} of {count} holdings scored",
                ),
                _portfolio_metric(
                    "Concentration",
                    f"{concentration:.1f}%" if concentration is not None else "N/A",
                    f"Largest position · {largest['symbol']}" if largest else "No positions",
                    tone=concentration_tone,
                ),
            ],
            className="portfolio-metric-strip portfolio-design-engine-reference",
            **{"aria-label": "Portfolio summary", "data-design-system": "issue-075"},
        )
        # ── Holdings table ──
        rows = []
        for sym, h in holdings.items():
            invested = h["shares"] * h["price_at_add"]
            weight = invested / total_invested * 100 if total_invested > 0 else 0
            current_price = h.get("current_price") or h["price_at_add"]
            current_value = h["shares"] * current_price
            gain_pct = (
                (current_price - h["price_at_add"]) / h["price_at_add"] * 100
                if h["price_at_add"]
                else 0
            )
            gain_class = "pos" if gain_pct >= 0 else "neg"

            sharpe_val = None
            cached_analysis = analyses[sym]
            if cached_analysis:
                sharpe_val = (cached_analysis.get("risk") or {}).get("sharpe")
            sharpe_str = f"{sharpe_val:.2f}" if sharpe_val is not None else "—"
            sharpe_class = (
                "clr-green"
                if sharpe_val is not None and sharpe_val >= 1.0
                else "clr-amber"
                if sharpe_val is not None and sharpe_val >= 0
                else "clr-red"
                if sharpe_val is not None
                else "clr-muted"
            )

            rows.append(
                html.Tr(
                    [
                        html.Td(
                            html.Div(
                                [
                                    company_logo(
                                        sym,
                                        h.get("company") or sym,
                                        "company-logo company-logo--table",
                                    ),
                                    html.Span(sym),
                                ],
                                className="portfolio-symbol-identity",
                            ),
                            className="pcol-symbol",
                        ),
                        html.Td(
                            html.Div(
                                className="flex align-items-center gap-sm",
                                children=[
                                    html.Label(
                                        className="shares-input-label",
                                        children=[
                                            html.Span(f"Shares of {sym}", className="sr-only"),
                                            input_control(
                                                id={
                                                    "type": "shares-edit-input",
                                                    "index": f"{active}|{sym}",
                                                },
                                                type="number",
                                                value=h["shares"],
                                                min=5,
                                                step=1,
                                                debounce=False,
                                                className="shares-input",
                                            ),
                                        ],
                                    ),
                                    button(
                                        "✓",
                                        id={"type": "shares-save-btn", "index": f"{active}|{sym}"},
                                        n_clicks=0,
                                        className="shares-save-btn",
                                    ),
                                ],
                            )
                        ),
                        html.Td(
                            f"${h['price_at_add']:.2f}" if h["price_at_add"] else "N/A",
                            className="pcol-num",
                        ),
                        html.Td(f"${current_value:,.0f}", className="pcol-num"),
                        html.Td(f"{weight:.1f}%", className="pcol-num"),
                        html.Td(
                            sharpe_str,
                            className=f"pcol-score pcol-num {sharpe_class}",
                            title="Sharpe Ratio from last full analysis. ≥1.0 = good.",
                        ),
                        html.Td(
                            delta(gain_pct, label="Return"), className=f"pcol-return {gain_class}"
                        ),
                        html.Td(
                            button(
                                "✕",
                                n_clicks=0,
                                id={"type": "remove-holding-btn", "index": f"{active}|{sym}"},
                                className="portfolio-remove-btn",
                            )
                        ),
                    ],
                    id=f"portfolio-holding-{sym}",
                )
            )
        table = responsive_table(
            [
                html.Thead(
                    html.Tr(
                        [
                            html.Th("Symbol"),
                            html.Th("Shares"),
                            html.Th("Price"),
                            html.Th("Value"),
                            html.Th("Weight"),
                            html.Th("Sharpe"),
                            html.Th("Return"),
                            html.Th(""),
                        ]
                    )
                ),
                html.Tbody(rows),
            ],
            label=f"{active} portfolio holdings",
            sticky_identifier=True,
            className="portfolio-table",
        )
        table.className = "ds-table-wrap has-sticky-identifier portfolio-table-wrap"
        # ── Action buttons ──
        ready = count >= 10
        actions = mobile_action_bar(
            [
                button(
                    "🚀 Run Simulation" + (f" ({count}/10)" if not ready else ""),
                    id="run-simulation-btn",
                    className="portfolio-action-btn primary",
                    n_clicks=0,
                    disabled=(count == 0),
                ),
            ]
        )
        actions.className = "ds-mobile-actions portfolio-actions d-flex gap-8"
        header.children.append(actions)
        holdings_card = html.Section(
            [
                html.Div(
                    [html.Div([html.H2("Holdings"), html.P(f"{count} positions")])],
                    className="portfolio-card-header",
                ),
                table,
            ],
            className=(
                "portfolio-dashboard-card portfolio-card-span-3 portfolio-holdings-card"
            ),
        )
        content_grid = html.Div(
            [
                _portfolio_allocation_card(holdings, analyses, total_value),
                _portfolio_weak_link_card(weak_link),
                holdings_card,
            ],
            className="portfolio-content-grid",
        )
        body = html.Div(
            [summary_cards, portfolio_trust, content_grid],
            className="portfolio-body",
        )
    duration_ms = (_time.perf_counter() - started_at) * 1000
    performance_metrics.record_ui_operation(
        "portfolio-load",
        duration_ms,
        outcome="empty" if not holdings else "success",
        section="portfolio-holdings",
        first_useful_ms=duration_ms,
    )
    product_analytics.track_event(
        _telemetry_user_id(),
        "portfolio_first_useful",
        {"holding_count": count, "outcome": "empty" if not holdings else "success"},
    )
    return container([header, body], size="wide", className="portfolio-reference-layout")


# ── Remove holding ────────────────────────────────────────────────────────────
@callback(
    Output("portfolio-refresh-store", "data", allow_duplicate=True),
    Input({"type": "remove-holding-btn", "index": dash.ALL}, "n_clicks"),
    State("portfolio-refresh-store", "data"),
    prevent_initial_call=True,
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
    Output("portfolio-msg", "children", allow_duplicate=True),
    Input({"type": "shares-save-btn", "index": dash.ALL}, "n_clicks"),
    State({"type": "shares-edit-input", "index": dash.ALL}, "value"),
    State({"type": "shares-edit-input", "index": dash.ALL}, "id"),
    State("portfolio-refresh-store", "data"),
    prevent_initial_call=True,
)
def update_shares(n_clicks_list, values, ids, refresh):
    triggered = dash.ctx.triggered_id
    if not triggered or not any(n for n in n_clicks_list if n):
        return dash.no_update, dash.no_update
    triggered_index = triggered["index"]
    new_shares = None
    for id_dict, val in zip(ids, values, strict=False):
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


def _comparison_stats_row(bt: dict) -> html.Div:
    """Single-portfolio summary stats row (reused for side-by-side display)."""
    if bt.get("error"):
        return html.Div(f"❌ {bt['error']}", className="text-danger")

    def _delta(val, ref):
        d = val - ref
        sign = "+" if d >= 0 else ""
        delta_class = "clr-green fs-12" if d >= 0 else "clr-red fs-12"
        return html.Span(f" ({sign}${d:,.0f})", className=delta_class)

    return html.Div(
        className="portfolio-stats-row",
        children=[
            html.Div(
                className="stat-item",
                children=[
                    html.Div("Invested", className="stat-label"),
                    html.Div(f"${bt['total_invested']:,.2f}", className="stat-value"),
                ],
            ),
            html.Div(
                className="stat-item",
                children=[
                    html.Div("Portfolio Value", className="stat-label"),
                    html.Div(
                        [
                            html.Span(f"${bt['final_value']:,.2f}", className="stat-value"),
                            _delta(bt["final_value"], bt["total_invested"]),
                        ]
                    ),
                ],
            ),
            html.Div(
                className="stat-item",
                children=[
                    html.Div("SPY (same $)", className="stat-label"),
                    html.Div(
                        [
                            html.Span(f"${bt['final_spy']:,.2f}", className="stat-value"),
                            _delta(bt["final_spy"], bt["spy_invested"]),
                        ]
                    ),
                ],
            ),
            html.Div(
                className="stat-item",
                children=[
                    html.Div("Portfolio CAGR", className="stat-label"),
                    html.Div(
                        f"{bt['cagr']:+.1f}%",
                        className="stat-value " + ("clr-green" if bt["cagr"] > 0 else "clr-red"),
                    ),
                ],
            ),
            html.Div(
                className="stat-item",
                children=[
                    html.Div("SPY CAGR", className="stat-label"),
                    html.Div(
                        f"{bt['spy_cagr']:+.1f}%",
                        className="stat-value "
                        + ("clr-green" if bt["spy_cagr"] > 0 else "clr-red"),
                    ),
                ],
            ),
            html.Div(
                className="stat-item",
                children=[
                    html.Div("vs SPY", className="stat-label"),
                    html.Div(
                        f"{bt['cagr'] - bt['spy_cagr']:+.1f}% / yr",
                        className="stat-value "
                        + ("clr-green" if bt["cagr"] > bt["spy_cagr"] else "clr-red"),
                    ),
                ],
            ),
        ],
    )


def _comparison_holdings_table(bt: dict) -> html.Div:
    """Holdings detail table (reused for side-by-side display)."""
    if bt.get("error") or not bt.get("holdings_detail"):
        return html.Div()
    detail_rows = []
    for sym, d in bt["holdings_detail"].items():
        factor = d.get("split_factor", 1.0)
        orig = d.get("original_shares", d["shares"])
        if factor and factor != 1.0 and orig:
            split_label = f"÷{1 / factor:.0f}" if factor < 1 else f"×{factor:.4g}"
            shares_cell = html.Td(
                [
                    str(d["shares"]),
                    html.Span(f" (split {split_label})", className="fs-11 clr-amber ml-4"),
                ]
            )
        else:
            shares_cell = html.Td(str(d["shares"]))
        detail_rows.append(
            html.Tr(
                [
                    html.Td(sym, className="font-semibold text-info"),
                    shares_cell,
                    html.Td(f"${d['entry_price']:.2f}"),
                    html.Td(f"${d['current_price']:.2f}"),
                    html.Td(f"${d['current_value']:,.2f}"),
                    html.Td(
                        f"{d['gain_pct']:+.1f}%",
                        className="clr-green" if d["gain_pct"] >= 0 else "clr-red",
                    ),
                ]
            )
        )
    return html.Div(
        className="scorecard",
        children=[
            html.Div("Holdings Performance (10yr backtest period)", className="scorecard-header"),
            table(
                className="screener-table",
                caption="Holdings backtest performance",
                children=[
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Ticker"),
                                html.Th("Shares"),
                                html.Th("Entry Price"),
                                html.Th("Exit Price"),
                                html.Th("Value"),
                                html.Th("Total Return"),
                            ]
                        )
                    ),
                    html.Tbody(detail_rows),
                ],
            ),
        ],
    )


def _comparison_weak_link_card(user_id: str, port_name: str, bt: dict) -> html.Div:
    """Render counterfactual weak-link results without overstating tied impacts.

    One unique largest positive SPY-swap improvement is shown as the weak link.
    Other material underperformers remain drags. Equal largest impacts receive a
    tie explanation rather than the false claim that every holding beat SPY.
    """
    if bt.get("error"):
        return html.Div()
    p_obj = portfolio_engine.load_portfolio(user_id, port_name)
    if not p_obj:
        return html.Div()
    wl = portfolio_engine.analyze_weak_links(p_obj, bt)
    if wl.get("error"):
        return html.Div(
            f"⚠️  Weak-link analysis unavailable: {wl['error']}",
            className="clr-muted fs-13 py-8 px-4",
        )
    gap = wl["gap_cagr"]
    gap_col = GREEN if gap >= 0 else RED
    gap_text = (
        f"Portfolio CAGR {wl['port_cagr']:+.1f}%  vs  "
        f"SPY {wl['spy_cagr']:+.1f}%  —  {gap:+.2f}% / yr gap "
        f"over {wl['n_years']:.1f} yr"
    )
    if wl.get("weakest"):
        ws = wl["weakest"]
        wd = wl["holdings"][ws]
        banner = html.Div(
            f"⚠️  Weakest link: {ws} — "
            f"replacing it with SPY would have improved total returns "
            f"by +{wd['swap_delta_pct']:.2f}%",
            className="portfolio-weak-link-alert portfolio-weak-link-alert--danger br-6 px-14 py-8 mb-12 fs-13 fw-600",
        )
    elif any(
        details.get("swap_delta_pct", 0) > 0
        for details in wl.get("holdings", {}).values()
    ):
        banner = html.Div(
            "No unique weakest link — the largest counterfactual impacts are tied.",
            className=(
                "portfolio-weak-link-alert portfolio-weak-link-alert--danger "
                "br-6 px-14 py-8 mb-12 fs-13 fw-600"
            ),
        )
    else:
        banner = html.Div(
            "✅  No weak links — every holding beat SPY over the backtest period.",
            className="portfolio-weak-link-alert portfolio-weak-link-alert--safe br-6 px-14 py-8 mb-12 fs-13 fw-600",
        )
    wl_rows = []
    for sym in wl["ranking"]:
        d = wl["holdings"][sym]
        verdict = d["verdict"]
        v_icon = (
            "⚠️"
            if verdict in {"weak link", "drag"}
            else "✅"
            if verdict == "contributor"
            else "—"
        )
        wl_rows.append(
            html.Tr(
                [
                    html.Td(sym, className="font-semibold text-info"),
                    html.Td(f"{d['weight']:.1f}%"),
                    html.Td(
                        f"{d['stock_cagr']:+.1f}%",
                        className="clr-green" if d["stock_cagr"] >= 0 else "clr-red",
                    ),
                    html.Td(
                        f"{d['cagr_vs_spy']:+.1f}%",
                        className="clr-green" if d["cagr_vs_spy"] >= 0 else "clr-red",
                    ),
                    html.Td(
                        f"{d['drag_bps']:+.1f}",
                        className="clr-green" if d["drag_bps"] >= 0 else "clr-red",
                    ),
                    html.Td(
                        f"{d['swap_delta_pct']:+.2f}%",
                        className="clr-green" if d["swap_delta_pct"] <= 0 else "clr-red",
                    ),
                    html.Td(
                        f"{v_icon} {verdict}",
                        className=(
                            "clr-red fw-600"
                            if verdict == "weak link"
                            else "clr-green fw-600"
                            if verdict == "contributor"
                            else "clr-muted fw-600"
                        ),
                    ),
                ]
            )
        )
    return html.Div(
        className="scorecard",
        children=[
            html.Div("🔍 Weak Link Analysis", className="scorecard-header"),
            html.Div(gap_text, className=f"fs-13 mb-14 px-4 {tone_class(gap_col)}"),
            banner,
            table(
                className="screener-table",
                caption=f"{port_name} weak-link analysis",
                children=[
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Ticker"),
                                html.Th("Weight"),
                                html.Th("Stock CAGR"),
                                html.Th("vs SPY"),
                                html.Th("Drag (bps)"),
                                html.Th("Swap Δ"),
                                html.Th("Verdict"),
                            ]
                        )
                    ),
                    html.Tbody(wl_rows),
                ],
            ),
            html.Div(
                "Table sorted worst-to-best.  "
                "Drag (bps): weighted annualised underperformance vs SPY (negative = drag).  "
                "Swap Δ: total-return change if this stock were replaced with SPY "
                "(positive = stock was a drag; negative = stock beat SPY).",
                className="analysis-copy-leading fs-11 clr-muted mt-10 px-4",
            ),
        ],
    )


def _build_comparison_view(
    user_id: str, active: str, compare: str, cmp_result: dict, palette: list
) -> list:
    """
    Side-by-side comparison view: winner banner + 2-column layout for
    stats, combined backtest/Monte Carlo charts, holdings, and weak-link
    analysis. Reuses run_simulation()/analyze_weak_links() results from
    compare_portfolios() — no simulation logic is re-implemented.
    """
    sections = []

    # ── Winner banner ────────────────────────────────────────────────────
    winner = cmp_result.get("winner")
    score_a = cmp_result.get("score_a", 0)
    score_b = cmp_result.get("score_b", 0)
    reasons = cmp_result.get("reasons", [])
    if winner:
        title, title_color = f"🏆 {winner} is stronger", GREEN
    else:
        title, title_color = "Both portfolios perform similarly.", MUTED
    sections.append(
        html.Div(
            className=f"scorecard mt-24 portfolio-comparison-summary {tone_class(title_color)}",
            children=[
                html.Div(title, className="portfolio-comparison-title fs-15 fw-700"),
                html.Div(
                    [
                        html.Span(f"{active}: {score_a:.1f}", className="mr-16"),
                        html.Span(f"{compare}: {score_b:.1f}"),
                    ],
                    className="portfolio-comparison-copy fs-13 clr-muted",
                ),
                html.Ul(
                    [html.Li(r, className="fs-12 clr-text") for r in reasons],
                    className="portfolio-comparison-reasons m-0",
                ),
            ],
        )
    )

    sim_a = cmp_result["portfolio_a"]
    sim_b = cmp_result["portfolio_b"]
    bt_a, mc_a = sim_a["backtest"], sim_a["montecarlo"]
    bt_b, mc_b = sim_b["backtest"], sim_b["montecarlo"]
    color_a, color_b = palette[0], palette[1]

    # ── Column headers ───────────────────────────────────────────────────
    sections.append(
        _two_col(
            html.Div(f"📊 {active}", className=f"scorecard-header fs-16 {tone_class(color_a)}"),
            html.Div(f"📊 {compare}", className=f"scorecard-header fs-16 {tone_class(color_b)}"),
        )
    )

    # ── Side-by-side stats ───────────────────────────────────────────────
    sections.append(
        _two_col(
            _comparison_stats_row(bt_a),
            _comparison_stats_row(bt_b),
        )
    )

    # ── Combined backtest chart (A + B + single SPY line) ───────────────
    if not bt_a.get("error") and not bt_b.get("error"):
        fig_bt = go.Figure()
        fig_bt.add_trace(
            go.Scatter(
                x=bt_a["dates"],
                y=bt_a["portfolio_value"],
                name=active,
                line=dict(color=color_a, width=2.5),
            )
        )
        fig_bt.add_trace(
            go.Scatter(
                x=bt_b["dates"],
                y=bt_b["portfolio_value"],
                name=compare,
                line=dict(color=color_b, width=2.5),
            )
        )
        fig_bt.add_trace(
            go.Scatter(
                x=bt_a["dates"],
                y=bt_a["spy_value"],
                name="SPY",
                line=dict(color=MUTED, width=1.5, dash="dot"),
            )
        )
        fig_bt.update_layout(
            **_chart_layout(
                f"{active} vs {compare} vs SPY — 10yr Backtest (actual $)", many_traces=True
            )
        )
        fig_bt.update_yaxes(title_text="Portfolio Value ($)", tickprefix="$")
        sections.append(
            dcc.Graph(
                figure=fig_bt,
                config={"displayModeBar": False, "responsive": True},
                className="portfolio-graph",
            )
        )
    elif bt_a.get("error"):
        sections.append(html.Div(f"❌ {active}: {bt_a['error']}", className="text-danger"))
    elif bt_b.get("error"):
        sections.append(html.Div(f"❌ {compare}: {bt_b['error']}", className="text-danger"))

    # ── Combined Monte Carlo chart (A + B medians/bands + single SPY band) ──
    if not mc_a.get("error") and not mc_b.get("error"):
        fig_mc = go.Figure()
        # SPY band (grey) — from portfolio A's projection (same SPY series)
        fig_mc.add_trace(
            go.Scatter(
                x=mc_a["dates"] + mc_a["dates"][::-1],
                y=mc_a["spy_p90"] + mc_a["spy_p10"][::-1],
                fill="toself",
                fillcolor="rgba(158,158,158,0.12)",
                line=dict(color="rgba(0,0,0,0)"),
                name="SPY range",
                showlegend=True,
            )
        )
        fig_mc.add_trace(
            go.Scatter(
                x=mc_a["dates"],
                y=mc_a["spy_p50"],
                name="SPY median",
                line=dict(color=MUTED, width=1.5, dash="dot"),
            )
        )
        for mc, name, color in ((mc_a, active, color_a), (mc_b, compare, color_b)):
            r, g_c, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            fill_rgba = f"rgba({r},{g_c},{b},0.12)"
            fig_mc.add_trace(
                go.Scatter(
                    x=mc["dates"] + mc["dates"][::-1],
                    y=mc["p90"] + mc["p10"][::-1],
                    fill="toself",
                    fillcolor=fill_rgba,
                    line=dict(color="rgba(0,0,0,0)"),
                    name=f"{name} range",
                )
            )
            fig_mc.add_trace(
                go.Scatter(
                    x=mc["dates"],
                    y=mc["p50"],
                    name=f"{name} median",
                    line=dict(color=color, width=2.5),
                )
            )
        fig_mc.update_layout(
            **_chart_layout(
                f"{active} vs {compare} vs SPY — 2yr Monte Carlo Projection (1,000 paths)",
                many_traces=True,
            )
        )
        fig_mc.update_yaxes(title_text="Projected Value ($)", tickprefix="$")
        sections.append(
            dcc.Graph(
                figure=fig_mc,
                config={"displayModeBar": False, "responsive": True},
                className="portfolio-graph",
            )
        )

    # ── Side-by-side holdings tables ─────────────────────────────────────
    sections.append(
        _two_col(
            _comparison_holdings_table(bt_a),
            _comparison_holdings_table(bt_b),
        )
    )

    # ── Side-by-side weak-link analysis ──────────────────────────────────
    sections.append(
        _two_col(
            _comparison_weak_link_card(user_id, active, bt_a),
            _comparison_weak_link_card(user_id, compare, bt_b),
        )
    )

    return sections


# ── Run simulation ────────────────────────────────────────────────────────────
def run_simulation(n, active, compare, *, _uid=None, _skip_guards=False):
    """Execute a simulation; the UI submits this helper as a resumable job."""
    if not n or not active:
        return [], None
    uid = _uid or get_user_id()
    if not _skip_guards:
        access = permissions.can_access_feature(uid, permissions.Feature.PORTFOLIO_ANALYTICS)
        if not access.allowed:
            product_analytics.track_event(
                uid,
                "upgrade_viewed",
                {
                    "feature": "portfolio_analytics",
                    "source": "portfolio_sim_lock",
                    "plan": "premium",
                },
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
            product_analytics.track_event(
                uid, "backtest_failed", {"source": "portfolio", "reason": "rate_limit"}
            )
            return html.Div(
                f"⏳ Portfolio simulation rate limit reached.{wait}", className="text-danger"
            ), None
    started_at = _time.perf_counter()
    product_analytics.track_event(
        uid,
        "backtest_started",
        {"source": "portfolio", "portfolio_name": active, "compare": compare or ""},
    )

    def _build_sim_charts(port_name: str, color: str) -> list:
        sim = portfolio_engine.run_simulation(uid, port_name)
        if sim.get("error"):
            return [html.Div(f"❌ {sim['error']}", className="text-danger")]
        bt = sim["backtest"]
        mc = sim["montecarlo"]
        components = []
        if not bt.get("error"):
            components.append(_comparison_stats_row(bt))
        # ── Backtest chart ─────────────────────────────────────────────────
        if not bt.get("error"):
            fig_bt = go.Figure()
            fig_bt.add_trace(
                go.Scatter(
                    x=bt["dates"],
                    y=bt["portfolio_value"],
                    name=port_name,
                    line=dict(color=color, width=2.5),
                )
            )
            fig_bt.add_trace(
                go.Scatter(
                    x=bt["dates"],
                    y=bt["spy_value"],
                    name="SPY",
                    line=dict(color=MUTED, width=1.5, dash="dot"),
                )
            )
            fig_bt.update_layout(
                **_chart_layout(f"{port_name} — 10yr Backtest vs SPY (actual $)", many_traces=True)
            )
            fig_bt.update_yaxes(title_text="Portfolio Value ($)", tickprefix="$")
            components.append(
                dcc.Graph(
                    figure=fig_bt,
                    config={"displayModeBar": False, "responsive": True},
                    className="portfolio-graph",
                )
            )
        # ── Monte Carlo chart ──────────────────────────────────────────────
        if not mc.get("error"):
            fig_mc = go.Figure()
            # SPY band (grey)
            fig_mc.add_trace(
                go.Scatter(
                    x=mc["dates"] + mc["dates"][::-1],
                    y=mc["spy_p90"] + mc["spy_p10"][::-1],
                    fill="toself",
                    fillcolor="rgba(158,158,158,0.12)",
                    line=dict(color="rgba(0,0,0,0)"),
                    name="SPY range",
                    showlegend=True,
                )
            )
            fig_mc.add_trace(
                go.Scatter(
                    x=mc["dates"],
                    y=mc["spy_p50"],
                    name="SPY median",
                    line=dict(color=MUTED, width=1.5, dash="dot"),
                )
            )
            # Portfolio band (colour)
            r, g_c, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            fill_rgba = f"rgba({r},{g_c},{b},0.15)"
            fig_mc.add_trace(
                go.Scatter(
                    x=mc["dates"] + mc["dates"][::-1],
                    y=mc["p90"] + mc["p10"][::-1],
                    fill="toself",
                    fillcolor=fill_rgba,
                    line=dict(color="rgba(0,0,0,0)"),
                    name=f"{port_name} range",
                )
            )
            fig_mc.add_trace(
                go.Scatter(
                    x=mc["dates"],
                    y=mc["p50"],
                    name=f"{port_name} median",
                    line=dict(color=color, width=2.5),
                )
            )
            fig_mc.add_trace(
                go.Scatter(
                    x=mc["dates"],
                    y=mc["p10"],
                    name="Worst case (p10)",
                    line=dict(color=color, width=1, dash="dash"),
                )
            )
            fig_mc.add_trace(
                go.Scatter(
                    x=mc["dates"],
                    y=mc["p90"],
                    name="Best case (p90)",
                    line=dict(color=color, width=1, dash="dash"),
                )
            )
            fig_mc.update_layout(
                **_chart_layout(
                    f"{port_name} — 2yr Monte Carlo Projection (1,000 paths)", many_traces=True
                )
            )
            fig_mc.update_yaxes(title_text="Projected Value ($)", tickprefix="$")
            components.append(
                dcc.Graph(
                    figure=fig_mc,
                    config={"displayModeBar": False, "responsive": True},
                    className="portfolio-graph",
                )
            )
        if not bt.get("error") and bt.get("holdings_detail"):
            components.append(_comparison_holdings_table(bt))
        if not bt.get("error"):
            components.append(_comparison_weak_link_card(uid, port_name, bt))
        return components

    PALETTE = [BLUE, GREEN, AMBER, "#e040fb", "#00bcd4"]
    if compare and compare != active:
        cmp_result = portfolio_engine.compare_portfolios(uid, active, compare)
        if cmp_result.get("error"):
            return [
                html.Div(f"📊 {active}", className="scorecard-header mt-24 fs-16"),
                *_build_sim_charts(active, PALETTE[0]),
                html.Div(
                    f"⚠️ Comparison unavailable: {cmp_result['error']}",
                    className="clr-muted fs-13 py-8 px-4 mt-16",
                ),
            ], None
        result = _build_comparison_view(uid, active, compare, cmp_result, PALETTE)
        permissions.record_feature_usage(
            uid, permissions.Feature.PORTFOLIO_ANALYTICS, usage_key=f"portfolio:{active}:{compare}"
        )
        product_analytics.track_event(
            uid,
            "backtest_completed",
            {"source": "portfolio", "portfolio_name": active, "compare": compare},
        )
        performance_metrics.record_ui_operation(
            "portfolio-simulation",
            (_time.perf_counter() - started_at) * 1000,
            section="portfolio-simulation",
            first_useful_ms=(_time.perf_counter() - started_at) * 1000,
        )
        return result, None
    result = [
        html.Div(f"📊 {active}", className="scorecard-header mt-24 fs-16"),
        *_build_sim_charts(active, PALETTE[0]),
    ]
    if not any(getattr(component, "className", None) == "text-danger" for component in result):
        permissions.record_feature_usage(
            uid, permissions.Feature.PORTFOLIO_ANALYTICS, usage_key=f"portfolio:{active}"
        )
        product_analytics.track_event(
            uid, "backtest_completed", {"source": "portfolio", "portfolio_name": active}
        )
    performance_metrics.record_ui_operation(
        "portfolio-simulation",
        (_time.perf_counter() - started_at) * 1000,
        outcome=(
            "partial"
            if any(getattr(component, "className", None) == "text-danger" for component in result)
            else "success"
        ),
        section="portfolio-simulation",
        first_useful_ms=(_time.perf_counter() - started_at) * 1000,
    )
    return result, None


@callback(
    Output("portfolio-sim-results", "children"),
    Output("portfolio-job-store", "data"),
    Output("upgrade-funnel-store", "data", allow_duplicate=True),
    Output("portfolio-job-cancel", "style"),
    Input("run-simulation-btn", "n_clicks"),
    State("portfolio-active-dropdown", "value"),
    State("portfolio-compare-dropdown", "value"),
    prevent_initial_call=True,
)
def start_simulation_job(n, active, compare):
    if not n or not active:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    uid = get_user_id()
    access = permissions.can_access_feature(uid, permissions.Feature.PORTFOLIO_ANALYTICS)
    if not access.allowed:
        locked, upgrade = run_simulation(n, active, compare)
        return locked, dash.no_update, upgrade, {"display": "none"}
    try:
            check_rate_limit(
                "portfolio_simulation",
                calls=PORTFOLIO_SIMULATION_CALLS,
                period_seconds=PORTFOLIO_SIMULATION_PERIOD_SECONDS,
                key=uid,
        )
    except RateLimited as exc:
        wait = f" Try again in {exc.retry_after} seconds." if exc.retry_after else ""
        return (
            html.Div(f"Portfolio simulation rate limit reached.{wait}", className="text-danger"),
            dash.no_update,
            None,
            {"display": "none"},
        )

    dedupe_key = json.dumps({"active": active, "compare": compare or ""}, sort_keys=True)

    def work(context):
        context.update("Loading portfolio holdings", completed_units=1)
        context.raise_if_cancelled()
        result = run_simulation(1, active, compare, _uid=uid, _skip_guards=True)
        context.update("Rendering simulation results", completed_units=2)
        return result

    snapshot = jobs.submit(
        operation="portfolio-simulation",
        owner=uid,
        dedupe_key=dedupe_key,
        work=work,
        total_units=2,
    )
    return (
        background_job_status(snapshot.public_dict()),
        snapshot.public_dict(),
        None,
        {"display": "inline-flex"},
    )


@callback(
    Output("portfolio-sim-results", "children", allow_duplicate=True),
    Output("portfolio-job-store", "data", allow_duplicate=True),
    Output("upgrade-funnel-store", "data", allow_duplicate=True),
    Output("portfolio-job-cancel", "style", allow_duplicate=True),
    Input("portfolio-job-interval", "n_intervals"),
    Input("portfolio-job-cancel", "n_clicks"),
    State("portfolio-job-store", "data"),
    prevent_initial_call=True,
)
def poll_simulation_job(_tick, cancel_clicks, stored):
    if not stored or not stored.get("job_id"):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    uid = get_user_id()
    job_id = stored["job_id"]
    if dash.ctx.triggered_id == "portfolio-job-cancel" and cancel_clicks:
        jobs.cancel(job_id, owner=uid)
    snapshot = jobs.snapshot(job_id, owner=uid)
    if snapshot is None:
        return section_error("This simulation is no longer available."), None, None, {"display": "none"}
    public = snapshot.public_dict()
    if snapshot.status == AsyncStatus.SUCCESS:
        result = jobs.result(job_id, owner=uid)
        if result is not None:
            return result[0], public, result[1], {"display": "none"}
    if snapshot.status == AsyncStatus.ERROR:
        return (
            section_error(
                "The simulation failed. You can retry without changing the portfolio.",
                technical_id=snapshot.error_code,
            ),
            public,
            None,
            {"display": "none"},
        )
    if snapshot.status == AsyncStatus.CANCELLED:
        return (
            empty_state(
                "Simulation cancelled", "Your portfolios and previous saved data were not changed."
            ),
            public,
            None,
            {"display": "none"},
        )
    return background_job_status(public), public, None, {"display": "inline-flex"}
