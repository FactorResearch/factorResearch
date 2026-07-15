"""Screener tab callbacks."""

import math
from urllib.parse import parse_qs

import dash
from dash import Input, Output, State, callback, html

from codes.data import db
from codes.data.us_indices import US_INDEX_DEFINITIONS, row_matches_any_index
from codes.engine import screener
from codes.engine.scorer import verdict_for_score
from codes.app_modules.analysis_ui import _fmt_market_cap, _fmt_updated
from codes.app_modules.company_identity import company_logo
from codes.app_modules.config import (
    GREEN, MUTED, PAGE_SIZE,
    get_score_class, get_verdict_class,
)
from codes.app_modules.screener_markets import (
    market_from_path,
    row_matches_market,
)
from codes.app_modules.session import get_portfolio_symbols
from codes.app_modules.session import get_user_id
from codes.services import product_analytics

last_progress_state = None
last_progress_bar_state = None


def _filter_results_by_market(results, market_code):
    return [r for r in results if row_matches_market(r, market_code)]


def _sector_from_search(search: str | None) -> str:
    sector = parse_qs((search or "").lstrip("?")).get("sector", [""])[0].strip()
    return sector[:100]


def _index_pill_buttons(selected_indices=None):
    selected = set(selected_indices or [])
    return [
        html.Button(
            index["label"],
            id={"type": "index-filter-pill", "index": index["value"]},
            className="screener-index-pill" + (" active" if index["value"] in selected else ""),
            n_clicks=0,
            type="button",
        )
        for index in US_INDEX_DEFINITIONS
    ]


def _quick_peek_row(symbol: str) -> dict | None:
    for row in screener.get_screener_results():
        if row.get("symbol") == symbol:
            return row
    return None


def _quick_peek_sections(row: dict, analysis: dict | None) -> list[html.Div]:
    if not analysis:
        return [
            html.Div(
                className="quick-peek-section",
                children=[
                    html.Div("Valuation", className="quick-peek-section-title"),
                    html.Div("Quick view only. Full valuation detail appears after a full analysis run.", className="quick-peek-section-copy"),
                ],
            ),
            html.Div(
                className="quick-peek-section",
                children=[
                    html.Div("Accounting", className="quick-peek-section-title"),
                    html.Div("Accounting diagnostics are not available yet for this cached screener row.", className="quick-peek-section-copy"),
                ],
            ),
            html.Div(
                className="quick-peek-section",
                children=[
                    html.Div("Risk", className="quick-peek-section-title"),
                    html.Div("Use the screener score as a first filter, then open the full report for drawdown and safety detail.", className="quick-peek-section-copy"),
                ],
            ),
            html.Div(
                className="quick-peek-section",
                children=[
                    html.Div("Growth", className="quick-peek-section-title"),
                    html.Div("Growth quality and capital allocation become available after full analysis.", className="quick-peek-section-copy"),
                ],
            ),
        ]

    graham = analysis.get("graham") or {}
    buffett = analysis.get("buffett") or {}
    piotroski = analysis.get("piotroski") or {}
    fcf_quality = analysis.get("fcf_quality") or {}
    altman = analysis.get("altman") or {}
    risk = analysis.get("risk") or {}
    growth_quality = analysis.get("growth_quality") or {}
    capital_allocation = analysis.get("capital_allocation") or {}
    earnings_revision = analysis.get("earnings_revision") or {}
    price = analysis.get("price")
    intrinsic = buffett.get("intrinsic_value")

    valuation_copy = "Intrinsic value not available yet."
    if price and intrinsic:
        direction = "below" if price <= intrinsic else "above"
        valuation_copy = f"Price is {direction} moat value. P/E {graham.get('pe', 0):.1f}x and P/B {graham.get('pb', 0):.2f}x frame the current setup."

    accounting_bits = []
    if piotroski.get("f_score") is not None:
        accounting_bits.append(f"F-Score {piotroski['f_score']}/9")
    if fcf_quality.get("fcf_quality_score") is not None:
        accounting_bits.append(f"FCF quality {fcf_quality['fcf_quality_score']:.0f}/100")
    if altman.get("zone_label"):
        accounting_bits.append(altman["zone_label"])
    accounting_copy = " · ".join(accounting_bits) or "Accounting diagnostics are limited for this report."

    risk_bits = []
    if risk.get("beta") is not None:
        risk_bits.append(f"Beta {risk['beta']:.2f}")
    if risk.get("sharpe") is not None:
        risk_bits.append(f"Sharpe {risk['sharpe']:.2f}")
    if altman.get("z_score") is not None:
        risk_bits.append(f"Altman {altman['z_score']:.2f}")
    risk_copy = " · ".join(risk_bits) or "Open full analysis for risk detail."

    growth_bits = []
    if growth_quality.get("growth_quality_score") is not None:
        growth_bits.append(f"Growth quality {growth_quality['growth_quality_score']:.0f}/100")
    if capital_allocation.get("capital_allocation_score") is not None:
        growth_bits.append(f"Capital allocation {capital_allocation['capital_allocation_score']:.0f}/100")
    if earnings_revision.get("total_score") is not None:
        growth_bits.append(f"Revisions {earnings_revision['total_score']:.0f}/100")
    growth_copy = " · ".join(growth_bits) or "Growth signals not available yet."

    return [
        html.Div(
            className="quick-peek-section",
            children=[
                html.Div("Valuation", className="quick-peek-section-title"),
                html.Div(valuation_copy, className="quick-peek-section-copy"),
            ],
        ),
        html.Div(
            className="quick-peek-section",
            children=[
                html.Div("Accounting", className="quick-peek-section-title"),
                html.Div(accounting_copy, className="quick-peek-section-copy"),
            ],
        ),
        html.Div(
            className="quick-peek-section",
            children=[
                html.Div("Risk", className="quick-peek-section-title"),
                html.Div(risk_copy, className="quick-peek-section-copy"),
            ],
        ),
        html.Div(
            className="quick-peek-section",
            children=[
                html.Div("Growth", className="quick-peek-section-title"),
                html.Div(growth_copy, className="quick-peek-section-copy"),
            ],
        ),
    ]


def _build_quick_peek(symbol: str) -> html.Div:
    row = _quick_peek_row(symbol) or {"symbol": symbol, "name": symbol, "sector": "Unknown", "composite_score": 0}
    analysis = db.get_analysis(symbol)
    enhanced = (analysis or {}).get("enhanced") or {}
    buffett = (analysis or {}).get("buffett") or {}
    price = (analysis or {}).get("price") or row.get("price")
    moat_value = buffett.get("intrinsic_value") or row.get("buffett_iv")
    verdict = enhanced.get("verdict")
    verdict_label = enhanced.get("verdict_label")
    score = enhanced.get("composite_score")

    if verdict is None:
        if row.get("analyzed"):
            verdict, verdict_label, _ = verdict_for_score(row.get("composite_score", 0), enhanced=False)
        else:
            verdict, verdict_label = "Pending", "pending"
    if score is None:
        score = row.get("composite_score", 0)

    metric_items = [
        ("Composite", f"{score:.0f}/100"),
        ("Verdict", verdict.replace("_", " ").title()),
        ("Price", f"{price:,.2f}" if price else "—"),
        ("Market Cap", _fmt_market_cap((analysis or {}).get("market_cap") or row.get("market_cap"))),
        ("Moat Value", f"{moat_value:,.2f}" if moat_value else "—"),
    ]

    return html.Div(
        className="quick-peek-card",
        children=[
            html.Div(
                className="quick-peek-identity",
                children=[
                    company_logo(symbol, row.get("name") or symbol, "company-logo company-logo--quick-peek"),
                    html.Div(className="quick-peek-identity-copy", children=[
                        html.Div(symbol, className="quick-peek-symbol"),
                        html.H4(row.get("name") or symbol, className="quick-peek-company"),
                        html.Div(
                            f"Updated {_fmt_updated((analysis or {}).get('updated_at') or row.get('updated_at'))}",
                            className="quick-peek-updated",
                        ),
                    ]),
                ],
            ),
            html.Div(
                className="quick-peek-metrics",
                children=[
                    html.Div(
                        className="quick-peek-metric",
                        children=[
                            html.Div(label, className="quick-peek-metric-label"),
                            html.Div(value, className="quick-peek-metric-value"),
                        ],
                    )
                    for label, value in metric_items
                ],
            ),
            html.Div(
                className="quick-peek-actions",
                children=[
                    html.Button(
                        "Open Full Analysis",
                        id="quick-peek-open-analysis-btn",
                        className="quick-peek-open-analysis-btn",
                        n_clicks=0,
                        type="button",
                    )
                ],
            ),
        ],
    )


# ── Screener ticker-click → quick peek ───────────────────────────────────────
@callback(
    Output("screener-quick-peek-symbol", "data"),
    Input(
        {"type": "screener-ticker-btn", "index": dash.ALL, "source": dash.ALL},
        "n_clicks",
    ),
    Input("quick-peek-close-btn", "n_clicks"),
    Input("quick-peek-backdrop", "n_clicks"),
    prevent_initial_call=True
)
def manage_quick_peek(n_clicks_list, close_clicks, backdrop_clicks):
    triggered = dash.ctx.triggered_id
    if isinstance(triggered, str) and triggered in {
        "quick-peek-close-btn",
        "quick-peek-backdrop",
    }:
        return None
    triggered_value = dash.ctx.triggered[0].get("value") if dash.ctx.triggered else None
    if not isinstance(triggered_value, (int, float)) or triggered_value <= 0:
        return dash.no_update
    if not isinstance(triggered, dict) or "index" not in triggered:
        return dash.no_update
    symbol = triggered["index"]
    try:
        product_analytics.track_event(get_user_id(), "stock_viewed", {"symbol": symbol, "source": "screener"})
    except Exception:
        pass
    return symbol


@callback(
    Output("screener-quick-peek-shell", "className"),
    Output("screener-quick-peek-content", "children"),
    Input("screener-quick-peek-symbol", "data"),
    prevent_initial_call=False,
)
def render_quick_peek(symbol):
    if not symbol:
        return "quick-peek-shell", html.Div(
            "Select a stock to open a quick summary without leaving the screener.",
            className="quick-peek-empty",
        )
    return "quick-peek-shell is-open", _build_quick_peek(symbol)


@callback(
    Output("screener-open-analysis-symbol", "data"),
    Output("screener-quick-peek-symbol", "data", allow_duplicate=True),
    Input("quick-peek-open-analysis-btn", "n_clicks"),
    State("screener-quick-peek-symbol", "data"),
    prevent_initial_call=True,
)
def open_full_analysis_from_peek(n_clicks, symbol):
    if not n_clicks or not symbol:
        return dash.no_update, dash.no_update
    return symbol, None


@callback(
    Output("index-filter", "data", allow_duplicate=True),
    Output("sector-filter", "value", allow_duplicate=True),
    Input("url", "pathname"),
    Input("url", "search"),
    prevent_initial_call=True
)
def reset_filters_for_market(pathname, search):
    market = market_from_path(pathname)
    try:
        product_analytics.track_event(
            get_user_id(),
            "screener_filter_changed",
            {"filter": "country", "value": market.code},
        )
    except Exception:
        pass
    return [], _sector_from_search(search)


@callback(
    Output("index-filter", "data", allow_duplicate=True),
    Input({"type": "index-filter-pill", "index": dash.ALL}, "n_clicks"),
    State("index-filter", "data"),
    prevent_initial_call=True
)
def update_index_filter(n_clicks_list, selected_indices):
    triggered = dash.ctx.triggered_id
    if not triggered or not any(n for n in n_clicks_list if n):
        return dash.no_update
    value = triggered["index"]
    selected = list(selected_indices or [])
    if value in selected:
        return [item for item in selected if item != value]
    if len(selected) >= 2:
        return dash.no_update
    return selected + [value]


@callback(
    Output("index-filter-pill-container", "children"),
    Input("index-filter", "data"),
    prevent_initial_call=False
)
def render_index_filter_pills(selected_indices):
    return _index_pill_buttons(selected_indices)


@callback(
    Output({"type": "screener-market-link", "index": dash.ALL}, "className"),
    Input("url", "pathname"),
    State({"type": "screener-market-link", "index": dash.ALL}, "id"),
    prevent_initial_call=False,
)
def style_screener_market_links(pathname, link_ids):
    active_code = market_from_path(pathname).code
    return [
        "screener-country-tab" + (" active" if link_id.get("index") == active_code else "")
        for link_id in (link_ids or [])
    ]


@callback(
    Output("screener-progress-info", "children"),
    Output("screener-progress-interval", "disabled", allow_duplicate=True),
    Output("screener-ready-store", "data"),
    Input("screener-progress-interval", "n_intervals"),
    State("screener-ready-store", "data"),
    prevent_initial_call=True
)
def update_progress(n, ready_val):
    global last_progress_state
    prog = screener.get_progress()
    prog_key = (prog["running"], prog["total"], prog["done"], prog["current"])
    if prog_key == last_progress_state:
        return dash.no_update, dash.no_update, dash.no_update
    last_progress_state = prog_key
    interval_disabled = not prog["running"] and prog["done"] > 0
    # Bump screener-ready-store whenever loading has finished so the table
    # rebuilds correctly both after initial load AND after a page refresh.
    # We encode the last signalled count as a negative number to distinguish
    # "never signalled" (0) from "signalled for N stocks" (-N).
    current_done = prog["done"]
    already_signalled = (ready_val or 0) < 0 and abs(ready_val or 0) == current_done
    if interval_disabled and current_done > 0 and not already_signalled:
        new_ready = -current_done
    else:
        new_ready = dash.no_update
    if not prog["running"] and prog["total"] == 0:
        return html.Div([
            html.Span("🟢 Ready", className="text-muted"),
        ], className="flex align-items-center gap-md"), True, new_ready
    if prog["running"]:
        pct = int(prog["done"] / prog["total"] * 100) if prog["total"] else 0
        phase_label = {
            "cached": "⚡ Scoring cached stocks",
        }.get(prog.get("phase", ""), "🔄 Processing")
        return html.Div([
            html.Span(f"{phase_label}: {prog['current']}", className="font-semibold text-info"),
            html.Span(f"({prog['done']}/{prog['total']} — {pct}%)", className="text-xs text-muted"),
        ], className="flex align-items-center gap-md"), False, dash.no_update
    else:
        if prog["done"] > 0:
            return html.Div([
                html.Span("✅ Analysis complete", className="font-semibold text-success"),
                html.Span(f"{prog['done']} stocks analyzed", className="text-xs text-muted"),
            ], className="flex align-items-center gap-md"), True, new_ready
        else:
            return "", True, new_ready

@callback(
    Output("screener-progress", "children"),
    Input("screener-progress-interval", "n_intervals"),
    prevent_initial_call=True
)
def update_progress_bar(n):
    global last_progress_bar_state
    prog = screener.get_progress()
    prog_key = (prog["running"], prog["total"], prog["done"])
    if prog_key == last_progress_bar_state:
        return dash.no_update
    last_progress_bar_state = prog_key
    if prog["total"] == 0:
        return []
    pct = int(prog["done"] / prog["total"] * 100) if prog["total"] else 0
    if not prog["running"] and pct == 0:
        return []
    remaining_stocks = prog["total"] - prog["done"]
    eta_seconds = int(remaining_stocks * 0.35)
    minutes, seconds = divmod(eta_seconds, 60)
    eta_text = f"~{minutes}m {seconds:02d}s remaining" if prog["running"] and eta_seconds > 0 else (
        "Complete" if not prog["running"] else "Almost done..."
    )
    return html.Div(className="progress-container mb-3xl", children=[
        html.Div([
            html.Span("Processing Universe Data", className="font-semibold"),
            html.Span(f"({pct}%) {eta_text}", className="text-xs text-muted")
        ], className="flex justify-between mb-lg"),
        html.Div(className="progress-bar-wrapper", children=[
            html.Progress(value=str(pct), max="100", className="progress-bar-fill")
        ])
    ])

@callback(
    Output("screener-table-container", "children"),
    Output("sector-filter", "options"),
    Output("screener-page-store", "data", allow_duplicate=True),
    Input("screener-ready-store",  "data"),
    Input("url",                       "pathname"),
    Input("page-load-interval",    "n_intervals"),
    Input("index-filter",          "data"),
    Input("sector-filter",         "value"),
    Input("screener-sort-store",   "data"),
    Input("screener-page-store",   "data"),
    State("screener-viewed-store", "data"),
    prevent_initial_call=True
)
def render_screener_table(ready, pathname, n_load, selected_indices, sector_filter, sort_state, page_num, viewed_data):
    triggered_id = dash.ctx.triggered_id
    active_market = market_from_path(pathname)
    results = _filter_results_by_market(screener.get_screener_results(), active_market.code)
   
    prog       = screener.get_progress()
    viewed_set = frozenset(viewed_data or [])
    sort_col   = (sort_state or {}).get("col", "composite_score")
    sort_asc   = (sort_state or {}).get("asc", False)
    page = page_num or 1
    # Reset to page 1 when filters/sorts change
    page_reset = dash.no_update
    
    if dash.ctx.triggered_id in ["index-filter", "sector-filter", "screener-sort-store", "url"]:
        page = 1
        page_reset = 1
    index_filtered_results = [r for r in results if row_matches_any_index(r, selected_indices)]
    sectors = sorted(set(r["sector"] for r in index_filtered_results if r.get("sector")))
    sector_options = [{"label": "All Sectors", "value": ""}] + [
        {"label": s, "value": s} for s in sectors
    ]
    if not results:
        if active_market.code != "US":
            return (
                html.Div([
                    html.Div(f"No {active_market.label} screener data loaded yet.",
                             className="clr-muted fw-600 mb-8"),
                    html.Div(f"Load verified {active_market.label} data into the market database, then refresh this view.",
                             className="clr-muted fs-13"),
                ], className="tac p-40"),
                sector_options,
                page_reset,
            )
        if prog["running"]:
            return (
                html.Div([
                    html.Div("⚡ Loading in background…",
                             className="clr-blue fw-600 mb-8"),
                    html.Div("Table will appear automatically when loading finishes.",
                             className="clr-muted fs-13"),
                ], className="tac p-40"),
                sector_options,
                page_reset,
            )
        return (
            html.Div("Screener is waiting for cached universe data.",
                     className="text-center p-4xl text-muted"),
            sector_options,
            page_reset,
        )
    portfolio_symbols = get_portfolio_symbols()
    filtered = [
        r for r in index_filtered_results
        if not sector_filter or r.get("sector") == sector_filter
    ]
    
    text_cols = {"symbol", "name", "sector", "updated_at"}
    if sort_col in text_cols:
        filtered = sorted(filtered, key=lambda r: (r.get(sort_col) or "").lower(), reverse=not sort_asc)
    else:
        filtered = sorted(filtered, key=lambda r: r.get(sort_col) or 0, reverse=not sort_asc)
    if triggered_id in {"screener-ready-store", "page-load-interval", "index-filter", "sector-filter", "screener-sort-store", "url"}:
        try:
            product_analytics.track_event(
                get_user_id(),
                "screener_run",
                {
                    "country": active_market.code,
                    "indices": selected_indices or [],
                    "sector": sector_filter or "",
                    "sort_col": sort_col,
                    "sort_asc": sort_asc,
                    "result_count": len(filtered),
                },
            )
        except Exception:
            pass
    SORT_COLS = [
        ("#",           None,               None),
        ("Ticker",      "symbol",           "Stock ticker symbol. Click to run full analysis."),
        ("Company",     "name",             "Company name."),
        ("Sector",      "sector",           "Industry sector from SEC filings."),
        ("Market Cap ↕","market_cap",       "Market capitalization (price × shares outstanding, $M). Populated after running full analysis on a stock."),
        ("Composite ↕", "composite_score",  "Composite score (0–100): weighted blend of the orthogonal scoring pillars. Pre-analysis uses FairValue+Quality only; run full analysis to include momentum, quality, forward revisions, growth, risk, and safety signals."),
        ("Fair Value ↕",  "graham_number",    "Fair Value — intrinsic value estimate: √(22.5 × EPS × BVPS). Green = current price is below this number (margin of safety exists). Populated after running full analysis on a stock."),
        ("Economic Moat Rating ↕","buffett_iv",       "Economic Moat Rating — two-stage DCF on owner earnings (FCF/share or EPS) at 12% discount rate, 3% terminal growth. Green = current price is below IV. Populated after running full analysis on a stock."),
        ("Updated",     "updated_at",       "Date this stock was last fully analyzed."),
        ("Verdict",     None,               "Investment verdict based on composite score: HIGH CONVICTION ≥75 · FAVORABLE ≥60 · BALANCED ≥45 · CAUTION ≥30 · UNFAVORABLE <30. * = fundamentals only (momentum not yet loaded)."),
    ]
    header_cells = []
    for label, sort_key, tooltip in SORT_COLS:
        th_class = "ch" if tooltip else ""
        th_class = f"{th_class} table-tooltip" if tooltip else th_class
        if sort_key:
            header_cells.append(html.Th(
                html.Button(
                    label,
                    id={"type": "screener-sort-btn", "index": sort_key},
                    className="sort-header-btn", n_clicks=0,
                    title=tooltip or "",
                ),
                title=tooltip or "", className=th_class,
            ))
        else:
            header_cells.append(html.Th(label, title=tooltip or "", className=th_class))
    rows = []
    accordion_items = []
    # Pagination — show PAGE_SIZE rows for the current page
    total_rows = len(filtered)
    total_pages = max(1, math.ceil(total_rows / PAGE_SIZE))
    page = min(max(1, page), total_pages)
    start_idx = (page - 1) * PAGE_SIZE
    page_filtered = filtered[start_idx:start_idx + PAGE_SIZE]

    for i, r in enumerate(page_filtered, start_idx + 1):
        sym     = r["symbol"]
        viewed  = sym in viewed_set
        in_port = bool(portfolio_symbols.get(sym))
        verdict       = r["verdict"]
        verdict_label = r["verdict_label"]
        verdict       = r["verdict"]
       
        if not r.get("analyzed"):
            verdict, verdict_label = "—", "pending"
        elif verdict == "PENDING":
            score = r["composite_score"]
            verdict, verdict_label, _ = verdict_for_score(score, enhanced=False)
            verdict = f"{verdict}*"
        badges = []
        port_list = portfolio_symbols.get(sym, [])
        for pname in port_list:
            badges.append(html.Span(f"💼 {pname}", className="portfolio-name-badge fs-10 clr-amber"))
        # n_clicks on <td> not <button> — iOS Safari drops touch on <button> inside <table>
        ticker_cell = html.Td(
            html.Div([
                company_logo(sym, r.get("name") or sym, "company-logo company-logo--table"),
                html.Div([
                    html.Span(sym, className="ticker-link-btn"),
                    html.Div(badges, className="d-flex gap-4 flex-wrap mt-3")
                    if badges else html.Div(),
                ]),
            ], className="ticker-identity"),
            id={"type": "screener-ticker-btn", "index": sym, "source": "table"},
            n_clicks=0,
            className="ticker-cell ticker-cell-touch cp",
        )
        # Graham Number cell — populated after full analysis
        gn    = r.get("graham_number")
        price = r.get("price")
        currency = r.get("currency") or "USD"
        grade = None
        intrinsic_score = None
        if gn and price:
            intrinsic_score = min(105, max(0, int(gn / price * 50)))
            grade = "A" if intrinsic_score >= 80 else "B" if intrinsic_score >= 65 else "C" if intrinsic_score >= 50 else "D" if intrinsic_score >= 35 else "F"
            grade_class = {"A": "clr-green", "B": "clr-blue", "C": "clr-amber", "D": "clr-red", "F": "clr-red"}.get(grade, "clr-muted")
            gn_cell = html.Td([
                html.Span(grade, className=f"fw-700 mr-4 {grade_class}"),
                html.Span(f"{intrinsic_score}/{105}", className="clr-muted fs-11"),
            ], title=f"Intrinsic Value Estimate · #{intrinsic_score}/105")
        elif gn:
            gn_cell = html.Td(
                f"{currency} {gn:,.2f}",
                className="text-xs",
                title="Fundamental fair value; live price not loaded",
            )
        else:
            gn_cell = html.Td("—", className="text-xs text-muted",
                              title="Run full analysis to calculate Intrinsic Value")
        # Buffett IV / Moat cell — populated after full analysis
        biv = r.get("buffett_iv")
        if biv:
            biv_color = GREEN if (price and price <= biv) else MUTED
            biv_class = "clr-green" if (price and price <= biv) else "clr-muted"
            biv_cell = html.Td([
                html.Div(className="moat-tip moat-tip-anchor ch d-inline-block", children=[
                    html.Span([html.Span(f"${biv:.0f}", className=f"fw-600 {biv_class}"), html.Span(" · Moat", className="ml-4 fs-11 clr-muted")]),
                    html.Span("Price below intrinsic value ✓" if (price and price <= biv) else "Price above intrinsic value",
                              className="moat-tip-popup d-none fs-11 wsnw py-6 px-10"),
                ]),
            ], title=f"Economic Moat: ${biv:.2f}")
        else:
            biv_cell = html.Td("—", className="text-xs text-muted",
                               title="Run full analysis to calculate Intrinsic Value")
        row_class = "screener-row--portfolio" if in_port else "screener-row--viewed" if viewed else ""
        
        rows.append(html.Tr(className=row_class, children=[
            html.Td(str(i), className="rank-num"),
            ticker_cell,
            html.Td(r["name"][:30], className="company-name-cell", title=r["name"]),
            html.Td(r["sector"][:18], className="text-xs text-muted",title=r["sector"]),
            html.Td(_fmt_market_cap(r.get("market_cap")), className="text-xs"),
            html.Td(
                html.Span(f"{r['composite_score']:.0f}", className=f"score-pill {get_score_class(r['composite_score'])}")
                if r.get("analyzed")
                else html.Span("—", className="score-pill")
            ),
            gn_cell,
            biv_cell,
            html.Td(_fmt_updated(r.get("updated_at")), className="text-xs text-muted"),
            html.Td(html.Span(verdict, className=f"verdict-pill {get_verdict_class(verdict_label)}")),
        ]))
        # ── Accordion item (mobile) ─────────────────────────────────────
        acc_biv_color = (GREEN if (price and biv and price <= biv) else MUTED) if biv else MUTED
        acc_biv_class = "clr-green" if (price and biv and price <= biv) else "clr-muted"
        acc_rows = [
            html.Div([html.Span("Company",   className="accordion-label"),
                      html.Span(r["name"],   className="accordion-value")], className="accordion-row"),
            html.Div([html.Span("Sector",    className="accordion-label"),
                      html.Span(r.get("sector","")[:28], className="accordion-value")], className="accordion-row"),
            html.Div([html.Span("Mkt Cap",   className="accordion-label"),
                      html.Span(_fmt_market_cap(r.get("market_cap")), className="accordion-value")], className="accordion-row"),
            html.Div([html.Span("Composite", className="accordion-label"),
                      html.Span(f"{r['composite_score']:.0f}",
                                className=f"score-pill {get_score_class(r['composite_score'])}")],
                     className="accordion-row"),
            html.Div([html.Span("Intrinsic",  className="accordion-label"),
                      html.Span(
                          f"{grade} {intrinsic_score}/105"
                          if gn and price
                          else f"{currency} {gn:,.2f}" if gn else "—",
                                className="accordion-value")],  className="accordion-row"),
            html.Div([html.Span("Moat", className="accordion-label"),
                      html.Span(f"${biv:.0f}" if biv else "—",
                                className="accordion-value " + acc_biv_class)], className="accordion-row"),
            html.Div([html.Span("Updated",   className="accordion-label"),
                      html.Span(_fmt_updated(r.get("updated_at")), className="accordion-value")], className="accordion-row"),
        ]
        if badges:
            acc_rows.append(html.Div(badges, className="accordion-portfolio-badges"))
        acc_rows.append(
            html.Div("→ Analyze", id={"type": "screener-ticker-btn", "index": sym, "source": "mobile"},
                     n_clicks=0, className="accordion-analyze-btn")
        )
        accordion_items.append(html.Details(
            className="accordion-item" + (" in-portfolio" if in_port else "") + (" viewed" if viewed else ""),
            children=[
                html.Summary(className="accordion-summary", children=[
                    html.Span(f"#{i}", className="accordion-rank"),
                    company_logo(sym, r.get("name") or sym, "company-logo company-logo--table"),
                    html.Span(sym, className="ticker-link-btn"),
                    html.Div([html.Span(verdict, className=f"verdict-pill {get_verdict_class(verdict_label)}")],
                             className="accordion-summary-right"),
                ]),
                html.Div(acc_rows, className="accordion-content"),
            ]
        ))
    n_analyzed  = sum(1 for r in filtered if r.get("analyzed"))
    n_portfolio = sum(1 for r in filtered if portfolio_symbols.get(r["symbol"]))
    note = html.Div([
        html.Span(f"{len(filtered):,} stocks", className="font-semibold"),
        html.Span(f" · {n_analyzed} analyzed · {n_portfolio} in portfolio"
                  " · * Verdict = fundamentals only — analyze individually to add Momentum",
                  className="text-muted"),
    ], className="fs-11 px-4 py-8 fsi")
    table = html.Table(className="screener-table", children=[
        html.Thead(html.Tr(children=header_cells)),
        html.Tbody(rows),
    ])
    # Pagination controls
    pagination = html.Div(className="pagination-controls", children=[
        html.Button(
            "◀ Prev",
            id={"type": "screener-page-btn", "index": "prev"},
            className="pagination-btn pagination-btn--prev",
            n_clicks=0,
            disabled=(page <= 1),
        ),
        html.Span(
            f"Page {page} of {total_pages}  ({total_rows:,} stocks)",
            className="pagination-info",
        ),
        html.Button(
            "Next ▶",
            id={"type": "screener-page-btn", "index": "next"},
            className="pagination-btn pagination-btn--next",
            n_clicks=0,
            disabled=(page >= total_pages),
        ),
    ])
    return html.Div([
        table,
        html.Div(accordion_items, className="screener-accordion"),
        note,
        pagination,
    ]), sector_options, page_reset

# ── Screener page navigation ──────────────────────────────────────────────────
@callback(
    Output("screener-page-store", "data"),
    Input({"type": "screener-page-btn", "index": dash.ALL}, "n_clicks"),
    State("screener-page-store", "data"),
    State("screener-sort-store", "data"),
    State("index-filter", "data"),
    State("sector-filter", "value"),
    State("url", "pathname"),
    prevent_initial_call=True
)
def navigate_screener_page(n_clicks_list, current_page, sort_state, selected_indices, sector_filter, pathname):
    triggered = dash.ctx.triggered_id
    if not triggered or not any(n for n in n_clicks_list if n):
        return dash.no_update
    market = market_from_path(pathname)
    results = _filter_results_by_market(screener.get_screener_results(), market.code)
    filtered = [
        r for r in results
        if row_matches_any_index(r, selected_indices)
        and (not sector_filter or r.get("sector") == sector_filter)
    ]
    total_pages = max(1, math.ceil(len(filtered) / PAGE_SIZE))
    cp = current_page or 1
    direction = triggered.get("index", "next")
    if direction == "prev":
        return max(1, cp - 1)
    return min(total_pages, cp + 1)

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
    text_cols = {"symbol", "name", "sector", "updated_at"}
    return {"col": col, "asc": col in text_cols}

@callback(
    Output("loading-trigger", "children"),
    Output("screener-progress-interval", "disabled"),
    Input("page-load-interval", "n_intervals"),
    prevent_initial_call=True
)
def sync_screener_interval_state(n_load):
    prog = screener.get_progress()
    if prog["running"] or prog["done"] > 0:
        return dash.no_update, False
    return dash.no_update, True



def register_clientside_callbacks(app):
    # Polls window.scrollY while the screener tab is visible and stores it so it
    # can be restored when the user navigates back.
    app.clientside_callback(
        """
        function(n_intervals) {
            var tab = document.getElementById('tab-screener');
            if (tab && tab.style.display !== 'none') {
                return window.scrollY;
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("screener-scroll-pos", "data"),
        Input("screener-scroll-poll-interval", "n_intervals"),
    )

    # Restore the saved scroll position when the screener tab becomes visible.
    # Analyze / Portfolio tabs always reset to top on switch.
    app.clientside_callback(
        """
        function(screener_style, analyze_style, portfolio_style, saved_pos) {
            if (screener_style && screener_style.display !== 'none') {
                requestAnimationFrame(function() {
                    window.scrollTo(0, saved_pos || 0);
                });
            } else if ((analyze_style && analyze_style.display !== 'none') ||
                       (portfolio_style && portfolio_style.display !== 'none')) {
                window.scrollTo(0, 0);
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("screener-scroll-restore-sink", "children"),
        Input("tab-screener", "style"),
        Input("tab-analyze", "style"),
        Input("tab-portfolio", "style"),
        State("screener-scroll-pos", "data"),
    )
