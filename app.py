"""
Graham Score App — Full Quant Version
Pure Python / Dash with SEC EDGAR + Alpha Vantage
Graham (40%) + Quality (35%) + Momentum (25%)
"""

import dash
from dash import dcc, html, Input, Output, State, callback
import plotly.graph_objects as go
import pandas as pd
import json
import shutil
from pathlib import Path

import cache
import sec_data
import graham
import quality
import momentum
import scorer
import screener
import universe
import alpha_vantage_client

# ── App Init ──────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    title="Graham Score — Quant",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}]
)
server = app.server

# ── Color Theme (CSS vars in style.css, keeping for reference) ────────────────

DARK, CARD, BORDER, GREEN, RED, AMBER, BLUE, TEXT, MUTED = (
    "#0f1117", "#1a1d27", "#2a2d3e", "#00c853", "#ff1744",
    "#ffc107", "#448aff", "#e0e0e0", "#9e9e9e"
)

# ── State ──────────────────────────────────────────────────────────────────────

_last_screener_results = None
_last_progress_state = None
_last_progress_bar_state = None

# ── Helpers ───────────────────────────────────────────────────────────────────

def analyze_stock(symbol: str) -> dict:
    """Full pipeline: SEC → Graham + Quality + (Price→Momentum) → Composite."""
    symbol = symbol.upper().strip()

    # Try cache
    cached = cache.read("analysis", symbol)
    if cached:
        return cached

    # Fetch SEC fundamentals
    try:
        sec_facts = sec_data.fetch_company_facts(symbol)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"SEC EDGAR error: {e}"}

    # Graham score (no price)
    g = graham.score(None, sec_facts)

    # Quality score (no price)
    q = quality.score(sec_facts)

    # Now try to get price
    price = alpha_vantage_client.get_price(symbol)
    hist = None
    spy_hist = None
    
    if price:
        # Recalculate Graham WITH price
        g = graham.score(price, sec_facts)
        
        # Fetch price history for charts (do this early to cache it)
        try:
            hist = alpha_vantage_client.get_price_history(symbol, years=10)
            spy_hist = alpha_vantage_client.get_price_history("SPY", years=10)
        except Exception as e:
            print(f"Price history fetch failed: {e}")

    # Momentum score (needs price history)
    m_result = {"total_score": 0, "total_max": 100, "criteria": []}
    if price and hist is not None:
        try:
            m_result = momentum.score(hist, spy_hist, symbol)
        except Exception as e:
            print(f"Momentum calculation failed: {e}")

    # Composite
    comp = scorer.composite(g, q, m_result)

    result = {
        "symbol":    symbol,
        "name":      sec_facts["name"],
        "sector":    sec_facts["sector"],
        "price":     price,
        "graham":    g,
        "quality":   q,
        "momentum":  m_result,
        "composite": comp,
        "price_history": hist.to_dict() if hist is not None else None,
        "spy_history": spy_hist.to_dict() if spy_hist is not None else None,
    }

    cache.write("analysis", symbol, result)
    return result


def get_score_class(pct: float) -> str:
    """CSS class for score coloring."""
    if pct >= 65:
        return "high"
    elif pct >= 35:
        return "medium"
    else:
        return "low"


def get_verdict_class(label: str) -> str:
    """CSS class for verdict coloring."""
    return label.lower().replace(" ", "-") if label else "pending"


# ── Layout ────────────────────────────────────────────────────────────────────

app.layout = html.Div(className="app-container", children=[

    # Header
    html.Div(className="app-header", children=[
        html.Div("📊", className="app-header-icon"),
        html.Div(className="app-header-content", children=[
            html.H1("Graham Score — Quant Edition"),
            html.P("Graham (40%) + Quality (35%) + Momentum (25%)")
        ])
    ]),

    # Tabs
    html.Div(className="tab-bar", children=[
        html.Button("📊 Screener", id="tab-screener-btn", className="tab-btn active"),
        html.Button("🔍 Analyze", id="tab-analyze-btn", className="tab-btn"),
    ]),

    # ── Tab: Screener ────────────────────────────────────────────────────────
    html.Div(id="tab-screener", className="screener-content", children=[
        html.Div(className="screener-toolbar", children=[
            html.Div(className="screener-controls", children=[
                html.Button(
                    "Load Universe (Russell 3000 + Microcap)",
                    id="load-universe-btn",
                    className="load-btn",
                    n_clicks=0,
                    disabled=False
                ),
                html.Div(id="screener-progress-info", className="screener-info"),
            ]),
            html.Div(className="screener-controls", style={"display": "flex", "gap": "10px", "alignItems": "center"}, children=[
                html.Label("Filter by sector:", style={"fontSize": "13px", "color": MUTED}),
                dcc.Dropdown(
                    id="sector-filter",
                    options=[{"label": "All Sectors", "value": ""}],
                    value="",
                    clearable=False,
                    style={
                        "background": CARD,
                        "border": f"1px solid {BORDER}",
                        "borderRadius": "10px",
                        "color": TEXT,
                        "width": "200px"
                    }
                ),
            ]),
        ]),

        html.Div(id="screener-progress", style={"marginBottom": "16px"}),

        dcc.Loading(
            id="screener-loading",
            type="default",
            color=BLUE,
            children=[
                html.Div(id="screener-table-container", className="screener-table-wrap", children=[
                    html.Div("Loading screener data...", style={"textAlign": "center", "padding": "40px", "color": MUTED})
                ])
            ]
        ),
    ], style={"display": "block"}),

    # ── Tab: Analyze ─────────────────────────────────────────────────────────
    html.Div(id="tab-analyze", className="main-content", children=[
        html.Div(className="search-section", children=[
            html.Div(className="search-container", children=[
                html.Div(className="search-input-wrapper", children=[
                    dcc.Input(
                        id="ticker-input",
                        type="text",
                        placeholder="Enter stock ticker (e.g. KO, JNJ, XOM)",
                        debounce=False,
                        className="ticker-input",
                        disabled=False
                    ),
                    html.Button("Analyze", id="analyze-btn", className="analyze-btn", disabled=False)
                ]),
                html.Div(id="status-msg", className="status-msg"),
            ]),
        ]),

        html.Div(id="history-section", className="history-section"),
        
        dcc.Loading(
            id="analysis-loading",
            type="default",
            color=BLUE,
            children=[
                html.Div(id="analysis-content", children=[])
            ]
        ),
    ], style={"display": "none"}),

    # Stores
    dcc.Store(id="screener-cache"),
    dcc.Store(id="analysis-store"),
    dcc.Store(id="screener-sort-store", data={"col": "composite_score", "asc": False}),
    dcc.Store(id="search-history-store"),
    dcc.Store(id="screener-click-ticker"),   # symbol clicked in screener table
    # interval disabled=True once loading finishes to stop constant re-renders
    dcc.Interval(id="screener-progress-interval", interval=2000, disabled=True),
    dcc.Loading(id="loading", type="circle", color=BLUE, children=html.Div(id="loading-trigger"))
])


# ── Tab Navigation ───────────────────────────────────────────────────────────

@callback(
    Output("tab-screener", "style"),
    Output("tab-analyze", "style"),
    Output("tab-screener-btn", "className"),
    Output("tab-analyze-btn", "className"),
    Input("tab-screener-btn", "n_clicks"),
    Input("tab-analyze-btn", "n_clicks"),
    Input("screener-click-ticker", "data"),
    prevent_initial_call=False
)
def switch_tabs(n_screener, n_analyze, clicked_ticker):
    triggered = dash.ctx.triggered_id
    # A ticker click always opens the Analyze tab
    if triggered == "screener-click-ticker" and clicked_ticker:
        return (
            {"display": "none"},
            {"display": "block"},
            "tab-btn",
            "tab-btn active"
        )
    if triggered == "tab-analyze-btn":
        return (
            {"display": "none"},
            {"display": "block"},
            "tab-btn",
            "tab-btn active"
        )
    # Default: screener tab
    return (
        {"display": "block"},
        {"display": "none"},
        "tab-btn active",
        "tab-btn"
    )


# ── Screener ticker-click → store ─────────────────────────────────────────────

@callback(
    Output("screener-click-ticker", "data"),
    Input({"type": "screener-ticker-btn", "index": dash.ALL}, "n_clicks"),
    prevent_initial_call=True
)
def capture_screener_click(n_clicks_list):
    # Find which button was just clicked
    triggered = dash.ctx.triggered_id
    if not triggered or not any(n for n in n_clicks_list if n):
        return dash.no_update
    return triggered["index"]  # the symbol string


# ── Screener ──────────────────────────────────────────────────────────────────

@callback(
    Output("screener-progress-info", "children"),
    Output("screener-progress-interval", "disabled", allow_duplicate=True),
    Input("screener-progress-interval", "n_intervals"),
    prevent_initial_call=True
)
def update_progress(n):
    global _last_progress_state

    prog = screener.get_progress()
    prog_key = (prog["running"], prog["total"], prog["done"], prog["current"])

    if prog_key == _last_progress_state:
        return dash.no_update, dash.no_update

    _last_progress_state = prog_key

    # Disable interval once loading is fully complete
    interval_disabled = not prog["running"] and prog["done"] > 0

    if not prog["running"] and prog["total"] == 0:
        return html.Div([
            html.Span("🟢 Ready to load universe", style={"color": MUTED}),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px"}), True

    if prog["running"]:
        pct = int(prog["done"] / prog["total"] * 100) if prog["total"] else 0
        return html.Div([
            html.Span(f"🔄 Processing: {prog['current']}", style={"color": BLUE, "fontWeight": "600"}),
            html.Span(f"({prog['done']}/{prog['total']} — {pct}%)", style={"color": MUTED, "fontSize": "12px"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px"}), False
    else:
        if prog["done"] > 0:
            return html.Div([
                html.Span("✅ Analysis complete", style={"color": GREEN, "fontWeight": "600"}),
                html.Span(f"{prog['done']} stocks analyzed", style={"color": MUTED, "fontSize": "12px"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "8px"}), True
        else:
            return "", True


@callback(
    Output("screener-progress", "children"),
    Input("screener-progress-interval", "n_intervals"),
    prevent_initial_call=True
)
def update_progress_bar(n):
    global _last_progress_bar_state

    prog = screener.get_progress()
    prog_key = (prog["running"], prog["total"], prog["done"])

    if prog_key == _last_progress_bar_state:
        return dash.no_update

    _last_progress_bar_state = prog_key

    if prog["total"] == 0:
        return []

    pct = int(prog["done"] / prog["total"] * 100) if prog["total"] else 0

    if not prog["running"] and pct == 0:
        return []

    remaining_stocks = prog["total"] - prog["done"]
    eta_seconds = int(remaining_stocks * 0.35)
    eta_text = f"~{eta_seconds}s remaining" if prog["running"] and eta_seconds > 0 else (
        "Complete" if not prog["running"] else "Almost done..."
    )

    return html.Div(className="progress-container", children=[
        html.Div([
            html.Span("Processing Universe Data", style={"fontWeight": "600", "color": TEXT}),
            html.Span(f"({pct}%) {eta_text}", style={"color": MUTED, "fontSize": "12px"})
        ], style={"display": "flex", "justifyContent": "spaceBetween", "marginBottom": "8px"}),
        html.Div(className="progress-bar-wrapper", children=[
            html.Div(className="progress-bar-fill", style={"width": f"{pct}%"})
        ])
    ], style={"marginBottom": "20px"})


@callback(
    Output("screener-table-container", "children"),
    Output("sector-filter", "options"),
    Input("screener-progress-interval", "n_intervals"),
    Input("sector-filter", "value"),
    Input("screener-sort-store", "data"),
    prevent_initial_call=True
)
def render_screener_table(n, sector_filter, sort_state):
    global _last_screener_results

    prog = screener.get_progress()
    results = screener.get_screener_results()

    # Only re-render when results set or running state actually changes
    sort_col = (sort_state or {}).get("col", "composite_score")
    sort_asc = (sort_state or {}).get("asc", False)
    state_key = (prog["running"], len(results), sector_filter or "", sort_col, sort_asc)
    if state_key == _last_screener_results:
        return dash.no_update, dash.no_update

    _last_screener_results = state_key

    # Rebuild sector dropdown options
    sectors = sorted(set(r["sector"] for r in results if r.get("sector")))
    sector_options = [{"label": "All Sectors", "value": ""}] + [
        {"label": s, "value": s} for s in sectors
    ]

    if prog["running"]:
        return (
            html.Div("Loading universe data...",
                     style={"textAlign": "center", "padding": "40px", "color": BLUE, "fontWeight": "600"}),
            sector_options
        )

    if not results:
        return (
            html.Div("Click 'Load Universe' to start analysis",
                     style={"textAlign": "center", "padding": "40px", "color": MUTED}),
            sector_options
        )

    # Apply sector filter
    filtered = [r for r in results if not sector_filter or r.get("sector") == sector_filter]

    # Apply sort
    sort_col = (sort_state or {}).get("col", "composite_score")
    sort_asc = (sort_state or {}).get("asc", False)
    text_cols = {"symbol", "name", "sector"}
    if sort_col in text_cols:
        filtered = sorted(filtered, key=lambda r: (r.get(sort_col) or "").lower(), reverse=not sort_asc)
    else:
        filtered = sorted(filtered, key=lambda r: r.get(sort_col) or 0, reverse=not sort_asc)

    # ── Sortable column headers ───────────────────────────────────────────────
    # Each sortable column renders as a button; the sort-store callback handles
    # re-ordering. Non-sortable cols (#, Verdict) are plain <th>.
    SORT_COLS = [
        ("#",         None),
        ("Ticker",    "symbol"),
        ("Company",   "name"),
        ("Sector",    "sector"),
        ("Graham ↕",  "graham_pct"),
        ("Quality ↕", "quality_pct"),
        ("Composite ↕", "composite_score"),
        ("Verdict",   None),
    ]

    header_cells = []
    for label, sort_key in SORT_COLS:
        if sort_key:
            header_cells.append(html.Th(
                html.Button(
                    label,
                    id={"type": "screener-sort-btn", "index": sort_key},
                    className="sort-header-btn",
                    n_clicks=0,
                )
            ))
        else:
            header_cells.append(html.Th(label))

    rows = []
    for i, r in enumerate(filtered, 1):
        # fundamental_only() returns "PENDING" — derive a label from the score
        verdict = r["verdict"]
        verdict_label = r["verdict_label"]
        if verdict == "PENDING":
            score = r["composite_score"]
            if score >= 70:
                verdict, verdict_label = "STRONG BUY*", "strong-buy"
            elif score >= 55:
                verdict, verdict_label = "BUY*", "buy"
            elif score >= 40:
                verdict, verdict_label = "WATCH*", "watch"
            elif score >= 25:
                verdict, verdict_label = "WEAK*", "hold"
            else:
                verdict, verdict_label = "AVOID*", "avoid"

        rows.append(html.Tr(children=[
            html.Td(str(i), className="rank-num"),
            html.Td(
                html.Button(
                    r["symbol"],
                    id={"type": "screener-ticker-btn", "index": r["symbol"]},
                    className="ticker-link-btn",
                    n_clicks=0,
                ),
                className="ticker-cell"
            ),
            html.Td(r["name"][:30], className="company-name-cell", title=r["name"]),
            html.Td(r["sector"][:18], style={"fontSize": "12px", "color": MUTED}),
            html.Td(html.Span(f"{r['graham_pct']:.0f}", className=f"score-pill {get_score_class(r['graham_pct'])}")),
            html.Td(html.Span(f"{r['quality_pct']:.0f}", className=f"score-pill {get_score_class(r['quality_pct'])}")),
            html.Td(html.Span(f"{r['composite_score']:.0f}", className=f"score-pill {get_score_class(r['composite_score'])}")),
            html.Td(html.Span(verdict, className=f"verdict-pill {get_verdict_class(verdict_label)}")),
        ]))

    note = html.Div(
        f"Showing all {len(filtered):,} stocks. * Verdict based on fundamentals only (Graham + Quality). Analyze individually to include Momentum.",
        style={"fontSize": "11px", "color": MUTED, "padding": "8px 4px", "fontStyle": "italic"}
    )

    table = html.Table(className="screener-table", children=[
        html.Thead(html.Tr(children=header_cells)),
        html.Tbody(rows)
    ])

    return html.Div([table, note]), sector_options



# ── Screener column sort ──────────────────────────────────────────────────────

@callback(
    Output("screener-sort-store", "data"),
    Input({"type": "screener-sort-btn", "index": dash.ALL}, "n_clicks"),
    State("screener-sort-store", "data"),
    prevent_initial_call=True
)
def update_sort(n_clicks_list, sort_state):
    triggered = dash.ctx.triggered_id
    if not triggered or not any(n for n in n_clicks_list if n):
        return dash.no_update
    col = triggered["index"]
    # Toggle direction if same col clicked again, else default desc for scores,
    # asc for text columns
    if sort_state and sort_state.get("col") == col:
        return {"col": col, "asc": not sort_state["asc"]}
    text_cols = {"symbol", "name", "sector"}
    return {"col": col, "asc": col in text_cols}


@callback(
    Output("loading-trigger", "children"),
    Output("screener-progress-interval", "disabled"),
    Input("load-universe-btn", "n_clicks"),
    prevent_initial_call=True
)
def load_universe(n_clicks):
    if n_clicks and n_clicks > 0:
        screener.load_universe_background()
        return "", False   # enable the interval so progress callbacks fire
    return "", True


# ── Analyze ───────────────────────────────────────────────────────────────────

def _build_analysis_content(data: dict) -> list:
    """Render analysis data into Dash components. Pure function, no side effects."""
    if not data or "error" in data:
        return []

    symbol = data["symbol"]
    name   = data["name"]
    sector = data["sector"]
    g      = data["graham"]
    q      = data["quality"]
    m      = data["momentum"]
    comp   = data["composite"]
    price  = data.get("price")

    header = html.Div(className="company-header", children=[
        html.Div(className="company-header-left", children=[
            html.H2(name),
            html.Div(f"{symbol} · {sector}", className="company-meta"),
            html.Div(className="stats-row", children=[
                _stat("Price",     f"${price:.2f}"            if price              else "N/A"),
                _stat("P/E",       f"{g.get('pe', 0):.1f}×"  if g.get('pe')        else "N/A"),
                _stat("P/B",       f"{g.get('pb', 0):.2f}×"  if g.get('pb')        else "N/A"),
                _stat("ROE",       f"{q.get('roe', 0):.1f}%" if q.get('roe')       else "N/A"),
                _stat("Op Margin", f"{q.get('op_margin', 0):.1f}%" if q.get('op_margin') else "N/A"),
            ])
        ]),
        html.Div(className="grade-badge", children=[
            html.Div(g["grade"], className="grade-letter",
                     style={"color": _grade_color(g["grade"])}),
            html.Div("Graham Grade", className="grade-label"),
            html.Div(f"{g['total_score']}/{g['total_max']}", className="grade-score"),
        ])
    ])

    composite_banner = html.Div(className="composite-banner", children=[
        html.Div([
            html.Div(comp["verdict"], className="composite-banner-verdict",
                     style={"color": _verdict_color(comp["verdict_label"])}),
            html.Div(comp["verdict_desc"], className="composite-banner-desc"),
        ]),
        html.Div(className="pillar-scores", children=[
            _pillar("Graham",   comp["graham_pct"],              "40%"),
            _pillar("Quality",  comp["quality_pct"],             "35%"),
            _pillar("Momentum", comp.get("momentum_pct") or "--","25%"),
            html.Div([
                html.Div(f"{comp['composite_score']:.0f}", className="pillar-value",
                         style={"fontSize": "28px"}),
                html.Div("Composite", className="pillar-label"),
            ])
        ])
    ])

    warnings = []
    if comp["value_trap_warning"]:
        warnings.append(html.Div(
            "⚠️ Value Trap Risk: Cheap but declining margins and weak momentum.",
            className="warning-banner"
        ))

    graham_card   = _render_scorecard("Graham Value Analysis", g["criteria"], "graham")
    quality_card  = _render_scorecard("Quality Analysis",      q["criteria"], "quality")
    momentum_card = (_render_scorecard("Momentum Analysis", m["criteria"], "momentum")
                     if m.get("criteria") else html.Div())

    charts_row = html.Div(className="charts-grid", children=[
        _eps_chart(g.get("eps_history", []), symbol),
        _price_chart(data.get("price_history"), data.get("spy_history"), symbol),
    ])

    div_chart      = _div_chart(g.get("div_history", []), symbol)
    graham_details = _graham_details_card(g)

    return [header, composite_banner] + warnings + [
        graham_card, quality_card, momentum_card,
        charts_row, div_chart, graham_details
    ]


@callback(
    Output("analysis-content", "children"),   # ← dcc.Loading wraps this; spinner fires immediately
    Output("analysis-store",   "data"),
    Output("status-msg",       "children"),
    Output("analyze-btn",      "disabled"),
    Output("ticker-input",     "disabled"),
    Output("ticker-input",     "value"),
    Input("analyze-btn",          "n_clicks"),
    Input("screener-click-ticker","data"),
    State("ticker-input",         "value"),
    prevent_initial_call=True
)
def run_analysis(n_clicks, clicked_ticker, ticker_input_value):
    """
    Single callback: fetch + score + render.
    Because analysis-content is a child of dcc.Loading(id='analysis-loading'),
    Dash shows the spinner for the entire duration of this callback — including
    all blocking network calls — so the UI never appears frozen.
    """
    triggered = dash.ctx.triggered_id

    if triggered == "screener-click-ticker" and clicked_ticker:
        ticker = clicked_ticker
    else:
        ticker = ticker_input_value

    if not ticker or not ticker.strip():
        return [], None, "❌ Please enter a ticker symbol.", False, False, dash.no_update

    symbol = ticker.strip().upper()
    result = analyze_stock(symbol)

    if "error" in result:
        return [], None, f"❌ {result['error']}", False, False, symbol

    content = _build_analysis_content(result)
    return (
        content,
        result,
        f"✅ {result['name']} ({symbol}) — Analysis complete",
        False, False, symbol,
    )


# ── UI Components ─────────────────────────────────────────────────────────────

def _stat(label, value):
    return html.Div([
        html.Div(label, className="stat-label"),
        html.Div(value, className="stat-value")
    ], className="stat-item")


def _pillar(label, score, weight):
    return html.Div([
        html.Div(f"{score}%", className="pillar-value") if isinstance(score, (int, float)) else html.Div(score, className="pillar-value"),
        html.Div(label, className="pillar-label"),
        html.Div(f"({weight})", className="pillar-weight"),
    ])


def _grade_color(grade: str) -> str:
    return {"A": GREEN, "B": BLUE, "C": AMBER, "D": RED}.get(grade, MUTED)


def _verdict_color(label: str) -> str:
    return {
        "strong-buy": GREEN,
        "buy": BLUE,
        "watch": AMBER,
        "hold": MUTED,
        "avoid": RED,
        "pending": MUTED,
    }.get(label, MUTED)


def _render_scorecard(title: str, criteria: list, card_type: str) -> html.Div:
    rows = []
    for c in criteria:
        score = c["score"]
        max_s = c["max"]
        pct = score / max_s * 100 if max_s else 0
        color = GREEN if pct >= 66 else AMBER if pct >= 33 else RED

        rows.append(html.Div(className="criterion-row", children=[
            html.Div([
                html.Div(c["label"], className="criterion-label"),
                html.Div(c["note"], className="criterion-note"),
                html.Div(className="score-bar", children=[
                    html.Div(className="score-bar-fill", style={
                        "width": f"{pct}%", "background": color
                    })
                ])
            ]),
            html.Div(f"{score}/{max_s}", className="criterion-pts", style={"color": color}),
        ]))

    return html.Div(className="scorecard", children=[
        html.Div(title, className="scorecard-header"),
        html.Div(rows)
    ])


def _eps_chart(eps_history: list, symbol: str) -> html.Div:
    if not eps_history:
        return html.Div(className="empty-card", children=[
            html.Div("EPS History", className="empty-card-title"),
            html.Div("No EPS data", className="empty-title"),
            html.Div("Insufficient data available", className="empty-msg"),
        ])

    df = pd.DataFrame(eps_history).sort_values("year")
    colors = [GREEN if v >= 0 else RED for v in df["value"]]

    fig = go.Figure(go.Bar(
        x=df["year"].astype(str), y=df["value"],
        marker_color=colors,
        text=[f"${v:.2f}" for v in df["value"]],
        textposition="outside"
    ))
    fig.update_layout(**_chart_layout(f"{symbol} EPS History (10yr)"))
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def _price_chart(price_history_dict, spy_history_dict, symbol: str) -> html.Div:
    # Convert stored dict data back to DataFrames
    hist = pd.DataFrame(price_history_dict) if price_history_dict else pd.DataFrame()
    spy_hist = pd.DataFrame(spy_history_dict) if spy_history_dict else pd.DataFrame()

    if hist.empty:
        return html.Div(className="empty-card", children=[
            html.Div("Price History", className="empty-card-title"),
            html.Div("No price data", className="empty-title"),
            html.Div("Insufficient history available", className="empty-msg"),
        ])

    fig = go.Figure()

    def _normalise(df):
        df = df.copy()
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df = df.dropna()
        if df.empty or df["Close"].iloc[0] <= 0:
            return df
        df["norm"] = df["Close"] / df["Close"].iloc[0] * 100
        return df

    hist = _normalise(hist)
    if not hist.empty:
        fig.add_trace(go.Scatter(
            x=hist["Date"], y=hist["norm"], name=symbol,
            line=dict(color=BLUE, width=2)
        ))

    if not spy_hist.empty:
        spy_hist = _normalise(spy_hist)
        if not spy_hist.empty:
            fig.add_trace(go.Scatter(
                x=spy_hist["Date"], y=spy_hist["norm"], name="SPY",
                line=dict(color=MUTED, width=1.5, dash="dot")
            ))

    fig.update_layout(**_chart_layout(f"{symbol} vs SPY (10yr normalised)"))
    fig.update_yaxes(title_text="Index (100 = start)")
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def _div_chart(div_history: list, symbol: str) -> html.Div:
    if not div_history:
        return html.Div(className="empty-card", children=[
            html.Div("Dividend History", className="empty-card-title"),
            html.Div("No dividends", className="empty-title"),
            html.Div("This company has not paid dividends", className="empty-msg"),
        ])

    df = pd.DataFrame(div_history).sort_values("year")
    df = df[df["value"] > 0]
    if df.empty:
        return html.Div(className="empty-card", children=[
            html.Div("Dividend History", className="empty-card-title"),
            html.Div("No dividends", className="empty-title"),
            html.Div("No dividend payments on record", className="empty-msg"),
        ])

    fig = go.Figure(go.Bar(
        x=df["year"].astype(str),
        y=df["value"] / 1e6,
        marker_color=BLUE,
        text=[f"${v/1e6:,.0f}M" for v in df["value"]],
        textposition="outside"
    ))
    fig.update_layout(**_chart_layout(f"{symbol} Dividend Payments (USD Millions)"))
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def _graham_details_card(data: dict) -> html.Div:
    gn = data.get("graham_number")
    price = data.get("price")
    mos = data.get("margin_of_safety")

    rows = [
        ("Graham Number", f"${gn:.2f}" if gn else "N/A"),
        ("Current Price", f"${price:.2f}" if price else "N/A"),
        ("Margin of Safety", f"{mos:.1f}%" if mos else "N/A"),
        ("EPS", f"${data.get('eps', 0):.2f}" if data.get('eps') else "N/A"),
        ("Book Value/Share", f"${data.get('bvps', 0):.2f}" if data.get('bvps') else "N/A"),
        ("Div Years", str(data.get("div_years", 0))),
        ("EPS Years", str(data.get("eps_years", 0))),
    ]

    color = GREEN if mos and mos > 0 else RED

    detail_rows = [
        html.Div(className="detail-row", children=[
            html.Span(label, className="detail-label"),
            html.Span(value, className="detail-value", style={"color": color if label == "Margin of Safety" else TEXT}),
        ])
        for label, value in rows
    ]

    return html.Div(className="detail-card", children=[
        html.Div("Graham Number Details", className="card-header"),
        html.Div(detail_rows)
    ])


def _chart_layout(title: str) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=13, color=MUTED), x=0),
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        font=dict(color=TEXT, family="Inter, system-ui, sans-serif"),
        margin=dict(l=16, r=16, t=40, b=16),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(gridcolor=BORDER, zeroline=False),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11),
                   orientation="h", x=0, y=1.1)
    )


# ── Startup ───────────────────────────────────────────────────────────────────

def startup():
    print("\n🚀 Graham Score — Quant Edition")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Graham (40%) + Quality (35%) + Momentum (25%)")
    print("SEC EDGAR (free) + Alpha Vantage (free)\n")

    sec_data.get_ticker_map()
    universe.get_universe()

    results = screener.load_cached_only()
    print(f"✅ {len(results)} cached stocks ready\n")


startup()

if __name__ == "__main__":
    app.run(debug=True, port=8050)