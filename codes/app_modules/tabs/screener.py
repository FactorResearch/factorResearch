"""Screener tab callbacks."""

import math
import time as _time
from datetime import date, timedelta
from urllib.parse import parse_qs

import dash
import plotly.graph_objects as go
from dash import Input, Output, State, callback, clientside_callback, dcc, html

from codes.app_modules.analysis_ui import _fmt_market_cap, _fmt_updated
from codes.app_modules.company_identity import company_logo
from codes.app_modules.config import (
    PAGE_SIZE,
    get_score_class,
    get_verdict_class,
)
from codes.app_modules.design_system.primitives import button, empty_state, table
from codes.app_modules.design_system.states import stage_progress
from codes.app_modules.screener_markets import (
    market_from_path,
    row_matches_market,
)
from codes.app_modules.session import get_portfolio_symbols, get_user_id
from codes.data import db
from codes.services import performance_metrics, product_analytics
from codes.services import screener_service as screener
from codes.services.screener_service import (
    US_INDEX_DEFINITIONS,
    row_matches_any_index,
    verdict_for_score,
)

last_progress_state = None
last_progress_bar_state = None

SCREENER_DEFAULT_COLUMNS = [
    "company",
    "market_cap",
    "composite_score",
    "graham_number",
    "buffett_iv",
    "updated_at",
    "verdict",
    "data_support",
]


def _filter_results_by_market(results, market_code):
    return [r for r in results if row_matches_market(r, market_code)]


def _sector_from_search(search: str | None) -> str:
    sector = parse_qs((search or "").lstrip("?")).get("sector", [""])[0].strip()
    return sector[:100]


def _screener_state_from_search(search: str | None) -> dict:
    params = parse_qs((search or "").lstrip("?"))
    valid_indexes = {item["value"] for item in US_INDEX_DEFINITIONS}
    indexes = [value for value in params.get("index", []) if value in valid_indexes][:2]
    try:
        page = max(1, int(params.get("page", ["1"])[0]))
    except (TypeError, ValueError):
        page = 1
    sort_col = params.get("sort", ["composite_score"])[0]
    valid_sorts = {
        "symbol",
        "name",
        "sector",
        "market_cap",
        "composite_score",
        "graham_number",
        "buffett_iv",
        "updated_at",
    }
    if sort_col not in valid_sorts:
        sort_col = "composite_score"
    return {
        "indexes": indexes,
        "sector": _sector_from_search(search),
        "page": page,
        "sort": {"col": sort_col, "asc": params.get("dir", ["desc"])[0] == "asc"},
    }


def _index_pill_buttons(selected_indices=None):
    selected = set(selected_indices or [])
    return [
        button(
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


def _verdict_presentation_label(verdict: object) -> str:
    normalized = str(verdict or "pending").lower().replace("_", "-").replace(" ", "-")
    return {
        "strong-buy": "high-conviction",
        "attractive": "favorable",
        "buy": "favorable",
        "hold": "cautious",
        "avoid": "unfavorable",
    }.get(normalized, normalized)


def _build_quick_peek(symbol: str, score_period: str = "5y") -> html.Div:
    """Build the quick peek using the selected long-term score window."""
    row = _quick_peek_row(symbol) or {
        "symbol": symbol,
        "name": symbol,
        "sector": "Unknown",
        "composite_score": 0,
    }
    analysis = screener.get_analysis(symbol)
    enhanced = (analysis or {}).get("enhanced") or {}
    buffett = (analysis or {}).get("buffett") or {}
    price = (analysis or {}).get("price") or row.get("price")
    moat_value = buffett.get("intrinsic_value") or row.get("buffett_iv")
    verdict = enhanced.get("verdict")
    score = enhanced.get("composite_score")

    if verdict is None:
        if row.get("analyzed"):
            verdict, _, _ = verdict_for_score(
                row.get("composite_score", 0), enhanced=False
            )
        else:
            verdict = "Pending"
    if score is None:
        score = row.get("composite_score", 0)

    try:
        history = db.list_composite_score_history(symbol, limit=365)
        cutoff_days = 365 * (5 if score_period == "5y" else 10)
        cutoff = date.today() - timedelta(days=cutoff_days)
        history = [
            item
            for item in history
            if not item.get("snapshot_date")
            or date.fromisoformat(str(item["snapshot_date"])[:10]) >= cutoff
        ]
    except Exception:
        history = []
    score_history = [float(item["composite_score"]) for item in history if item.get("composite_score") is not None]
    chart = _score_development_chart(score, score_history)
    return html.Div(className="quick-peek-detail-grid", children=[
        html.Section(className="quick-overview-card", **{"aria-labelledby": "quick-overview-title"}, children=[
            html.Div(className="quick-peek-section-title", children=[
                html.Span("A", className="quick-peek-section-index"),
                html.H3(f"Quick Overview – {row.get('name') or symbol} ({symbol})", id="quick-overview-title"),
            ]),
            html.Div(className="quick-overview-body", children=[
                html.Div(className="overview-score", children=[
                    html.Span("Composite Score"),
                    html.Strong([f"{score:.1f}", html.Small("/100")]),
                    html.Div(className="mini-divider"),
                    html.Div(className="overview-values", children=[
                        html.Div([html.Small("Industry Value"), html.B(f"{moat_value:,.2f}" if moat_value else "—")]),
                        html.Div([html.Small("Current Price"), html.B(f"{price:,.2f}" if price else "—")]),
                        html.Div([html.Small("Verdict"), html.B(verdict.replace("_", " ").title(), className="positive")]),
                    ]),
                    button("Open full analysis →", id="quick-peek-open-analysis-btn", className="quick-peek-open-analysis-btn", n_clicks=0),
                ]),
                html.Div(className="overview-verdict", children=[
                    html.Span("Verdict"), html.Strong(verdict.replace("_", " ").title(), className="positive"),
                ]),
                html.Div(className="overview-signals", children=[
                    html.Span("Available signals"),
                    html.Ul([
                        html.Li(f"✓ {row.get('sector') or 'Sector'} fundamentals loaded"),
                        html.Li("✓ Composite score available" if score else "ⓘ Score not available"),
                        html.Li("✓ Valuation data available" if moat_value else "ⓘ Valuation data pending"),
                    ]),
                    html.Span("Data status"),
                    html.P(f"Updated {_fmt_updated((analysis or {}).get('updated_at') or row.get('updated_at'))}"),
                ]),
            ]),
        ]),
        html.Section(className="score-development-card", **{"aria-labelledby": "score-development-title"}, children=[
            html.Div(className="quick-peek-section-title score-title", children=[
                html.Span("B", className="quick-peek-section-index"),
                html.H3(f"Score Development – {row.get('name') or symbol} ({symbol})", id="score-development-title"),
                dcc.Dropdown(
                    id="score-development-period",
                    options=[
                        {"label": "5 years", "value": "5y"},
                        {"label": "10 years", "value": "10y"},
                    ],
                    value=score_period,
                    clearable=False,
                    searchable=False,
                    className="score-period-select",
                ),
            ]),
            html.Div(className="score-development-body", children=[
                html.Div(className="score-side", children=[
                    html.Span("Current Score"), html.Strong([f"{score:.1f}", html.Small("/100")]),
                    html.Span("Trend"), html.B("Improving" if len(score_history) > 1 and score_history[-1] >= score_history[0] else "Unchanged", className="positive"),
                    html.Div(className="delta-box", children=[html.Strong(f"{(score_history[-1] - score_history[0]):+.1f} pts" if len(score_history) > 1 else "—"), html.Small("vs. first snapshot")]),
                ]),
                chart,
                html.Div(className="score-explainer", children=[
                    html.A("What drove the change?"),
                    html.P("Score development is based on recorded composite snapshots. New history appears after score updates."),
                    html.A("View score breakdown →"),
                ]),
            ]),
        ]),
    ])


def _score_development_chart(score: float, history: list[float]) -> dcc.Graph | html.Div:
    """Render the compact score trend using recorded snapshots when available."""
    if len(history) < 2:
        return html.Div("Score development will appear after the next score update.", className="score-chart-empty")
    figure = go.Figure(go.Scatter(
        x=list(range(1, len(history) + 1)),
        y=history,
        mode="lines+markers",
        line={"color": "#b18a54", "width": 2.5},
        marker={"color": "#b18a54", "size": 6},
        hovertemplate="Score: %{y:.0f}<extra></extra>",
    ))
    figure.update_layout(
        height=180,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis={"visible": False, "fixedrange": True},
        yaxis={"range": [0, 100], "gridcolor": "rgba(177,138,84,.18)", "fixedrange": True},
    )
    return html.Div(
        dcc.Graph(
            figure=figure,
            className="score-line-chart-plot",
            config={"displayModeBar": False, "responsive": True},
        ),
        className="score-line-chart",
        role="img",
        **{"aria-label": f"Score development chart, current score {score:.0f} out of 100"},
    )


# ── Screener ticker-click → quick peek ───────────────────────────────────────
@callback(
    Output("screener-quick-peek-symbol", "data"),
    Input(
        {"type": "screener-ticker-btn", "index": dash.ALL, "source": dash.ALL},
        "n_clicks",
    ),
    Input("quick-peek-close-btn", "n_clicks"),
    prevent_initial_call=True,
)
def manage_quick_peek(n_clicks_list, close_clicks):
    triggered = dash.ctx.triggered_id
    if isinstance(triggered, str) and triggered in {
        "quick-peek-close-btn",
    }:
        return None
    triggered_value = dash.ctx.triggered[0].get("value") if dash.ctx.triggered else None
    if not isinstance(triggered_value, (int, float)) or triggered_value <= 0:
        return dash.no_update
    if not isinstance(triggered, dict) or "index" not in triggered:
        return dash.no_update
    symbol = triggered["index"]
    try:
        product_analytics.track_event(
            get_user_id(), "stock_viewed", {"symbol": symbol, "source": "screener"}
        )
    except Exception:
        pass
    return symbol


@callback(
    Output("screener-quick-peek-shell", "className"),
    Output("screener-quick-peek-content", "children"),
    Input("screener-quick-peek-symbol", "data"),
    Input("score-development-period", "value", allow_optional=True),
    prevent_initial_call=False,
)
def render_quick_peek(symbol, score_period="5y"):
    if not symbol:
        return "quick-peek-shell", html.Div(
            "Select a stock to open a quick summary without leaving the screener.",
            className="quick-peek-empty",
        )
    return "quick-peek-shell is-open", _build_quick_peek(symbol, score_period or "5y")


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
    prevent_initial_call=True,
)
def reset_filters_for_market(pathname):
    market = market_from_path(pathname)
    try:
        product_analytics.track_event(
            get_user_id(),
            "screener_filter_changed",
            {"filter": "country", "value": market.code},
        )
    except Exception:
        pass
    return [], ""


@callback(
    Output("index-filter", "data", allow_duplicate=True),
    Output("sector-filter", "value", allow_duplicate=True),
    Output("screener-page-store", "data", allow_duplicate=True),
    Output("screener-sort-store", "data", allow_duplicate=True),
    Input("url", "pathname"),
    Input("url", "search"),
    prevent_initial_call=True,
)
def apply_url_filters_compatibly(_pathname, search):
    """Keep pre-reload Dash pages valid while applying query filters."""
    state = _screener_state_from_search(search)
    return state["indexes"], state["sector"], state["page"], state["sort"]


clientside_callback(
    """
    function(search) {
        var sector = new URLSearchParams(search || '').get('sector') || '';
        return sector.trim().slice(0, 100);
    }
    """,
    Output("sector-filter", "value"),
    Input("url", "search"),
    prevent_initial_call=False,
)


clientside_callback(
    """
    function(indexes, sector, page, sortState) {
        var url = new URL(window.location.href);
        url.searchParams.delete('index');
        (indexes || []).slice(0, 2).forEach(function(value) {
            url.searchParams.append('index', value);
        });
        if (sector) url.searchParams.set('sector', sector);
        else url.searchParams.delete('sector');
        if ((page || 1) > 1) url.searchParams.set('page', String(page));
        else url.searchParams.delete('page');
        var state = sortState || {};
        if (state.col && state.col !== 'composite_score') url.searchParams.set('sort', state.col);
        else url.searchParams.delete('sort');
        if (state.asc) url.searchParams.set('dir', 'asc');
        else url.searchParams.delete('dir');
        history.replaceState(history.state, '', url.pathname + url.search + url.hash);
        return url.search;
    }
    """,
    Output("screener-url-state-sink", "children"),
    Input("index-filter", "data"),
    Input("sector-filter", "value"),
    Input("screener-page-store", "data"),
    Input("screener-sort-store", "data"),
    prevent_initial_call=True,
)


@callback(
    Output("index-filter", "data", allow_duplicate=True),
    Input({"type": "index-filter-pill", "index": dash.ALL}, "n_clicks"),
    State("index-filter", "data"),
    prevent_initial_call=True,
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
    prevent_initial_call=False,
)
def render_index_filter_pills(selected_indices):
    return _index_pill_buttons(selected_indices)


@callback(
    Output("index-filter", "data", allow_duplicate=True),
    Output("sector-filter", "value", allow_duplicate=True),
    Input("screener-reset-filters", "n_clicks"),
    Input("screener-clear-all-btn", "n_clicks"),
    prevent_initial_call=True,
)
def clear_screener_filters(empty_state_clicks, toolbar_clicks):
    if not empty_state_clicks and not toolbar_clicks:
        return dash.no_update, dash.no_update
    return [], ""


@callback(
    Output("screener-filter-summary", "children"),
    Input("index-filter", "data"),
    Input("sector-filter", "value"),
)
def summarize_screener_filters(selected_indices, sector):
    count = len(selected_indices or []) + bool(sector)
    return f"Filters ({count} active)"


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
    prevent_initial_call=True,
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
        return (
            html.Div(
                [
                    html.Span("🟢 Ready", className="text-muted"),
                ],
                className="flex align-items-center gap-md",
            ),
            True,
            new_ready,
        )
    if prog["running"]:
        pct = int(prog["done"] / prog["total"] * 100) if prog["total"] else 0
        phase_label = {
            "cached": "⚡ Scoring cached stocks",
        }.get(prog.get("phase", ""), "🔄 Processing")
        return (
            html.Div(
                [
                    html.Span(
                        f"{phase_label}: {prog['current']}", className="font-semibold text-info"
                    ),
                    html.Span(
                        f"({prog['done']}/{prog['total']} — {pct}%)", className="text-xs text-muted"
                    ),
                ],
                className="flex align-items-center gap-md",
            ),
            False,
            dash.no_update,
        )
    else:
        if prog["done"] > 0:
            return (
                html.Div(
                    [
                        html.Span("✅ Analysis complete", className="font-semibold text-success"),
                        html.Span(
                            f"{prog['done']} stocks analyzed", className="text-xs text-muted"
                        ),
                    ],
                    className="flex align-items-center gap-md",
                ),
                True,
                new_ready,
            )
        else:
            return "", True, new_ready


@callback(
    Output("screener-progress", "children"),
    Input("screener-progress-interval", "n_intervals"),
    prevent_initial_call=True,
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
    eta_text = (
        f"~{minutes}m {seconds:02d}s remaining"
        if prog["running"] and eta_seconds > 0
        else ("Complete" if not prog["running"] else "Almost done...")
    )
    return html.Div(
        [
            stage_progress(
                f"Processing universe data · {eta_text}",
                completed=prog["done"],
                total=prog["total"],
            )
        ],
        className="progress-container mb-3xl",
    )


@callback(
    Output("screener-table-container", "children"),
    Output("sector-filter", "options"),
    Output("screener-page-store", "data", allow_duplicate=True),
    Output("screener-table-pagination", "children"),
    Input("screener-ready-store", "data"),
    Input("url", "pathname"),
    Input("page-load-interval", "n_intervals"),
    Input("index-filter", "data"),
    Input("sector-filter", "value"),
    Input("screener-sort-store", "data"),
    Input("screener-page-store", "data"),
    State("screener-viewed-store", "data"),
    State("screener-page-size", "value"),
    prevent_initial_call=True,
)
def render_screener_table(
    ready,
    pathname,
    n_load,
    selected_indices,
    sector_filter,
    sort_state,
    page_num,
    viewed_data,
    page_size=PAGE_SIZE,
):
    started_at = _time.perf_counter()
    triggered_id = dash.ctx.triggered_id
    active_market = market_from_path(pathname)
    results = _filter_results_by_market(screener.get_screener_results(), active_market.code)

    prog = screener.get_progress()
    viewed_set = frozenset(viewed_data or [])
    sort_col = (sort_state or {}).get("col", "composite_score")
    sort_asc = (sort_state or {}).get("asc", False)
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
                html.Div(
                    [
                        html.Div(
                            f"No {active_market.label} screener data loaded yet.",
                            className="clr-muted fw-600 mb-8",
                        ),
                        html.Div(
                            f"Load verified {active_market.label} data into the market database, then refresh this view.",
                            className="clr-muted fs-13",
                        ),
                    ],
                    className="tac p-40",
                ),
                sector_options,
                page_reset,
                [],
            )
        if prog["running"]:
            return (
                stage_progress(
                    "Loading verified universe data in the background",
                    completed=prog.get("done"),
                    total=prog.get("total"),
                ),
                sector_options,
                page_reset,
                [],
            )
        return (
            empty_state(
                "No screener data available",
                "Screener is waiting for cached verified-universe data. Refresh after ingestion completes.",
            ),
            sector_options,
            page_reset,
            [],
        )
    portfolio_symbols = get_portfolio_symbols()
    filtered = [
        r for r in index_filtered_results if not sector_filter or r.get("sector") == sector_filter
    ]
    if not filtered:
        performance_metrics.record_ui_operation(
            "screener-refresh",
            (_time.perf_counter() - started_at) * 1000,
            outcome="empty",
            section="screener-table",
        )
        return (
            empty_state(
                "No stocks match these filters",
                "The universe is loaded, but the active market, index, and sector filters return no matches. Clear or broaden a filter to continue.",
                action=button(
                    "Clear filters",
                    id="screener-reset-filters",
                    variant="secondary",
                ),
            ),
            sector_options,
            page_reset,
        )

    text_cols = {"symbol", "name", "sector", "updated_at"}
    if sort_col in text_cols:
        filtered = sorted(
            filtered, key=lambda r: (r.get(sort_col) or "").lower(), reverse=not sort_asc
        )
    else:
        filtered = sorted(filtered, key=lambda r: r.get(sort_col) or 0, reverse=not sort_asc)
    if triggered_id in {
        "screener-ready-store",
        "page-load-interval",
        "index-filter",
        "sector-filter",
        "screener-sort-store",
        "url",
    }:
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
    visible = set(SCREENER_DEFAULT_COLUMNS)
    SORT_COLS = [
        ("Company", "name", "Company name.", "company"),
        (
            "Market Cap",
            None,
            "Market capitalization (price × shares outstanding, $M). Populated after running full analysis on a stock.",
            "market_cap",
        ),
        (
            "Composite",
            None,
            "Composite score (0–100): weighted blend of the orthogonal scoring pillars. Pre-analysis uses FairValue+Quality only; run full analysis to include momentum, quality, forward revisions, growth, risk, and safety signals.",
            "composite_score",
        ),
        (
            "Fair Value ↕",
            "graham_number",
            "Fair Value — intrinsic value estimate: √(22.5 × EPS × BVPS). Green = current price is below this number (margin of safety exists). Populated after running full analysis on a stock.",
            "graham_number",
        ),
        (
            "Economic Moat Rating ↕",
            "buffett_iv",
            "Economic Moat Rating — two-stage DCF on owner earnings (FCF/share or EPS) at 12% discount rate, 3% terminal growth. Green = current price is below IV. Populated after running full analysis on a stock.",
            "buffett_iv",
        ),
        ("Updated", "updated_at", "Date this stock was last fully analyzed.", "updated_at"),
        (
            "Verdict",
            None,
            "Investment verdict based on composite score: HIGH CONVICTION ≥75 · FAVORABLE ≥60 · BALANCED ≥45 · CAUTION ≥30 · UNFAVORABLE <30. * = fundamentals only (momentum not yet loaded).",
            "verdict",
        ),
        (
            "Data Support",
            None,
            "Source support for the normalized screener row. Partial or unavailable inputs are not presented as fully supported.",
            "data_support",
        ),
    ]
    header_cells = []
    for label, sort_key, tooltip, key in SORT_COLS:
        if key != "rank" and key not in visible:
            continue
        th_class = "ch" if tooltip else ""
        th_class = f"{th_class} table-tooltip" if tooltip else th_class
        if sort_key:
            sort_state = (
                ("ascending" if sort_asc else "descending") if sort_col == sort_key else "none"
            )
            header_cells.append(
                html.Th(
                    button(
                        label,
                        id={"type": "screener-sort-btn", "index": sort_key},
                        className="sort-header-btn",
                        n_clicks=0,
                        title=tooltip or "",
                        **{
                            "aria-label": f"Sort by {label.replace(' ↕', '')}; currently {sort_state}"
                        },
                    ),
                    title=tooltip or "",
                    className=th_class,
                    scope="col",
                    **{"aria-sort": sort_state},
                )
            )
        else:
            header_cells.append(
                html.Th(label, title=tooltip or "", className=th_class, scope="col")
            )
    rows = []
    accordion_items = []
    page_size = int(page_size or PAGE_SIZE)
    # Pagination — show the selected number of rows for the current page.
    total_rows = len(filtered)
    total_pages = max(1, math.ceil(total_rows / page_size))
    page = min(max(1, page), total_pages)
    start_idx = (page - 1) * page_size
    page_filtered = filtered[start_idx : start_idx + page_size]

    for i, r in enumerate(page_filtered, start_idx + 1):
        sym = r["symbol"]
        viewed = sym in viewed_set
        in_port = bool(portfolio_symbols.get(sym))
        verdict = r["verdict"]
        verdict_label = _verdict_presentation_label(r.get("verdict"))
        verdict = r["verdict"]

        if not r.get("analyzed"):
            verdict, verdict_label = "—", "pending"
        elif verdict == "PENDING":
            score = r["composite_score"]
            verdict, verdict_label, _ = verdict_for_score(score, enhanced=False)
            verdict = f"{verdict}*"
        badges = []
        port_list = portfolio_symbols.get(sym, [])
        for pname in port_list:
            badges.append(
                html.Span(f"💼 {pname}", className="portfolio-name-badge fs-10 clr-amber")
            )
        # n_clicks on <td> not <button> — iOS Safari drops touch on <button> inside <table>
        company_cell = html.Td(
            html.Div(
                [
                    company_logo(sym, r.get("name") or sym, "company-logo company-logo--table"),
                    html.Span(r["name"][:30], className="company-name-text"),
                    html.Span(f"({sym})", className="company-ticker"),
                    html.Div(badges, className="d-flex gap-4 flex-wrap mt-3")
                    if badges
                    else html.Div(),
                ],
                className="ticker-identity",
            ),
            id={"type": "screener-ticker-btn", "index": sym, "source": "table"},
            n_clicks=0,
            className="company-name-cell ticker-cell ticker-cell-touch cp",
            role="button",
            tabIndex=0,
            **{"aria-label": f"Analyze {sym}, {r.get('name') or sym}"},
        )
        # Graham Number cell — populated after full analysis
        gn = r.get("graham_number")
        price = r.get("price")
        currency = r.get("currency") or "USD"
        grade = None
        intrinsic_score = None
        if gn and price:
            intrinsic_score = min(105, max(0, int(gn / price * 50)))
            grade = (
                "A"
                if intrinsic_score >= 80
                else "B"
                if intrinsic_score >= 65
                else "C"
                if intrinsic_score >= 50
                else "D"
                if intrinsic_score >= 35
                else "F"
            )
            grade_class = {
                "A": "clr-green",
                "B": "clr-blue",
                "C": "clr-amber",
                "D": "clr-red",
                "F": "clr-red",
            }.get(grade, "clr-muted")
            gn_cell = html.Td(
                [
                    html.Span(grade, className=f"fw-700 mr-4 {grade_class}"),
                    html.Span(f"{intrinsic_score}/{105}", className="clr-muted fs-11"),
                ],
                title=f"Intrinsic Value Estimate · #{intrinsic_score}/105",
            )
        elif gn:
            gn_cell = html.Td(
                f"{currency} {gn:,.2f}",
                className="text-xs",
                title="Fundamental fair value; live price not loaded",
            )
        else:
            gn_cell = html.Td(
                "—",
                className="text-xs text-muted",
                title="Run full analysis to calculate Intrinsic Value",
            )
        # Buffett IV / Moat cell — populated after full analysis
        biv = r.get("buffett_iv")
        if biv:
            biv_class = "clr-green" if (price and price <= biv) else "clr-muted"
            biv_cell = html.Td(
                [
                    html.Div(
                        className="moat-tip moat-tip-anchor ch d-inline-block",
                        children=[
                            html.Span(
                                [
                                    html.Span(f"${biv:.0f}", className=f"fw-600 {biv_class}"),
                                    html.Span(" · Moat", className="ml-4 fs-11 clr-muted"),
                                ]
                            ),
                            html.Span(
                                "Price below intrinsic value ✓"
                                if (price and price <= biv)
                                else "Price above intrinsic value",
                                className="moat-tip-popup d-none fs-11 wsnw py-6 px-10",
                            ),
                        ],
                    ),
                ],
                title=f"Economic Moat: ${biv:.2f}",
            )
        else:
            biv_cell = html.Td(
                "—",
                className="text-xs text-muted",
                title="Run full analysis to calculate Intrinsic Value",
            )
        row_class = (
            "screener-row--portfolio" if in_port else "screener-row--viewed" if viewed else ""
        )

        row_cells = {
            "company": company_cell,
            "sector": html.Td(r["sector"][:18], className="text-xs text-muted", title=r["sector"]),
            "market_cap": html.Td(_fmt_market_cap(r.get("market_cap")), className="text-xs"),
            "composite_score": html.Td(
                html.Span(
                    f"{r['composite_score']:.1f}",
                    className=f"score-pill {get_score_class(r['composite_score'])}",
                )
                if r.get("analyzed")
                else html.Span("—", className="score-pill")
            ),
            "graham_number": gn_cell,
            "buffett_iv": biv_cell,
            "updated_at": html.Td(
                _fmt_updated(r.get("updated_at")), className="text-xs text-muted"
            ),
            "verdict": html.Td(
                html.Span(verdict, className=f"verdict-pill {get_verdict_class(verdict_label)}")
            ),
            "data_support": html.Td(
                str(
                    r.get("data_confidence")
                    or ("Full analysis" if r.get("analyzed") else "Fundamentals only")
                )
                .replace("_", " ")
                .title(),
                className="text-xs text-muted",
            ),
        }
        rows.append(
            html.Tr(
                className=row_class,
                children=[
                    row_cells[key]
                    for key in SCREENER_DEFAULT_COLUMNS
                    if key in visible
                ],
            )
        )
        # ── Accordion item (mobile) ─────────────────────────────────────
        acc_biv_class = "clr-green" if (price and biv and price <= biv) else "clr-muted"
        acc_rows = [
            html.Div(
                [
                    html.Span("Company", className="accordion-label"),
                    html.Span(r["name"], className="accordion-value"),
                ],
                className="accordion-row",
            ),
            html.Div(
                [
                    html.Span("Sector", className="accordion-label"),
                    html.Span(r.get("sector", "")[:28], className="accordion-value"),
                ],
                className="accordion-row",
            ),
            html.Div(
                [
                    html.Span("Mkt Cap", className="accordion-label"),
                    html.Span(_fmt_market_cap(r.get("market_cap")), className="accordion-value"),
                ],
                className="accordion-row",
            ),
            html.Div(
                [
                    html.Span("Composite", className="accordion-label"),
                    html.Span(
                        f"{r['composite_score']:.1f}",
                        className=f"score-pill {get_score_class(r['composite_score'])}",
                    ),
                ],
                className="accordion-row",
            ),
            html.Div(
                [
                    html.Span("Intrinsic", className="accordion-label"),
                    html.Span(
                        f"{grade} {intrinsic_score}/105"
                        if gn and price
                        else f"{currency} {gn:,.2f}"
                        if gn
                        else "—",
                        className="accordion-value",
                    ),
                ],
                className="accordion-row",
            ),
            html.Div(
                [
                    html.Span("Moat", className="accordion-label"),
                    html.Span(
                        f"${biv:.0f}" if biv else "—", className="accordion-value " + acc_biv_class
                    ),
                ],
                className="accordion-row",
            ),
            html.Div(
                [
                    html.Span("Updated", className="accordion-label"),
                    html.Span(_fmt_updated(r.get("updated_at")), className="accordion-value"),
                ],
                className="accordion-row",
            ),
            html.Div(
                [
                    html.Span("Data support", className="accordion-label"),
                    html.Span(
                        str(
                            r.get("data_confidence")
                            or ("Full analysis" if r.get("analyzed") else "Fundamentals only")
                        )
                        .replace("_", " ")
                        .title(),
                        className="accordion-value",
                    ),
                ],
                className="accordion-row",
            ),
        ]
        if badges:
            acc_rows.append(html.Div(badges, className="accordion-portfolio-badges"))
        acc_rows.append(
            html.Div(
                "→ Analyze",
                id={"type": "screener-ticker-btn", "index": sym, "source": "mobile"},
                n_clicks=0,
                className="accordion-analyze-btn",
                role="button",
                tabIndex=0,
                **{"aria-label": f"Analyze {sym}, {r.get('name') or sym}"},
            )
        )
        accordion_items.append(
            html.Details(
                className="accordion-item"
                + (" in-portfolio" if in_port else "")
                + (" viewed" if viewed else ""),
                children=[
                    html.Summary(
                        className="accordion-summary",
                        children=[
                            html.Span(f"#{i}", className="accordion-rank"),
                            company_logo(
                                sym, r.get("name") or sym, "company-logo company-logo--table"
                            ),
                            html.Span(sym, className="ticker-link-btn"),
                            html.Div(
                                [
                                    html.Span(
                                        verdict,
                                        className=f"verdict-pill {get_verdict_class(verdict_label)}",
                                    )
                                ],
                                className="accordion-summary-right",
                            ),
                        ],
                    ),
                    html.Div(acc_rows, className="accordion-content"),
                ],
            )
        )
    n_analyzed = sum(1 for r in filtered if r.get("analyzed"))
    n_portfolio = sum(1 for r in filtered if portfolio_symbols.get(r["symbol"]))
    note = html.Div(
        [
            html.Span(f"{len(filtered):,} stocks", className="font-semibold"),
            html.Span(
                f"{len(selected_indices or []) + bool(sector_filter)} active filters",
                className="text-xs text-muted",
            ),
            html.Span(
                f" · {n_analyzed} analyzed · {n_portfolio} in portfolio"
                " · * Verdict = fundamentals only — analyze individually to add Momentum",
                className="text-muted",
            ),
        ],
        className="screener-note fs-11 px-4 py-8 fsi",
    )
    table_density = "comfortable"
    table_component = table(
        className=f"screener-table density-{table_density}",
        caption="Stock screener results",
        children=[
            html.Thead(html.Tr(children=header_cells)),
            html.Tbody(rows),
        ],
    )
    # Pagination controls
    first_visible_page = min(max(page - 1, 1), max(total_pages - 2, 1))
    visible_pages = range(first_visible_page, min(first_visible_page + 3, total_pages) + 1)
    pagination = html.Div(
        className="pagination-controls",
        children=[
            dcc.Dropdown(
                id="screener-page-size",
                options=[{"label": f"{size} per page", "value": size} for size in (5, 10, 15, 20)],
                value=page_size,
                clearable=False,
                searchable=False,
                className="pagination-page-size",
            ),
            button(
                "‹",
                id={"type": "screener-page-btn", "index": "prev"},
                className="pagination-btn pagination-btn--prev",
                n_clicks=0,
                disabled=(page <= 1),
                **{"aria-label": "Previous page"},
            ),
            *[
                button(
                    str(page_number),
                    id={"type": "screener-page-btn", "index": page_number},
                    className=f"pagination-btn {'is-current' if page_number == page else ''}",
                    n_clicks=0,
                    **{"aria-label": f"Page {page_number}", "aria-current": "page" if page_number == page else None},
                )
                for page_number in visible_pages
            ],
            button(
                "›",
                id={"type": "screener-page-btn", "index": "next"},
                className="pagination-btn pagination-btn--next",
                n_clicks=0,
                disabled=(page >= total_pages),
                **{"aria-label": "Next page"},
            ),
        ],
    )
    performance_metrics.record_ui_operation(
        "screener-refresh",
        (_time.perf_counter() - started_at) * 1000,
        section="screener-table",
        first_useful_ms=(_time.perf_counter() - started_at) * 1000,
    )
    return (
        html.Div(
            [
                table_component,
                html.Div(accordion_items, className="screener-accordion"),
            ]
        ),
        sector_options,
        page_reset,
        html.Div([note, pagination], className="screener-table-footer-inner"),
    )


# ── Screener page navigation ──────────────────────────────────────────────────
@callback(
    Output("screener-page-store", "data"),
    Input({"type": "screener-page-btn", "index": dash.ALL}, "n_clicks"),
    State("screener-page-store", "data"),
    State("screener-sort-store", "data"),
    State("index-filter", "data"),
    State("sector-filter", "value"),
    State("url", "pathname"),
    State("screener-page-size", "value"),
    prevent_initial_call=True,
)
def navigate_screener_page(
    n_clicks_list, current_page, sort_state, selected_indices, sector_filter, pathname,
    page_size=PAGE_SIZE,
):
    triggered = dash.ctx.triggered_id
    if not triggered or not any(n for n in n_clicks_list if n):
        return dash.no_update
    market = market_from_path(pathname)
    results = _filter_results_by_market(screener.get_screener_results(), market.code)
    filtered = [
        r
        for r in results
        if row_matches_any_index(r, selected_indices)
        and (not sector_filter or r.get("sector") == sector_filter)
    ]
    page_size = int(page_size or PAGE_SIZE)
    total_pages = max(1, math.ceil(len(filtered) / page_size))
    cp = current_page or 1
    direction = triggered.get("index", "next")
    if isinstance(direction, int):
        return max(1, min(total_pages, direction))
    if direction == "prev":
        return max(1, cp - 1)
    return min(total_pages, cp + 1)


@callback(
    Output("screener-page-store", "data", allow_duplicate=True),
    Input("screener-page-size", "value"),
    prevent_initial_call=True,
)
def reset_screener_page_for_page_size(_page_size):
    """Return to the first page when the visible row count changes."""
    return 1


# ── Screener column sort ──────────────────────────────────────────────────────
@callback(
    Output("screener-sort-store", "data"),
    Input({"type": "screener-sort-btn", "index": dash.ALL}, "n_clicks"),
    State("screener-sort-store", "data"),
    prevent_initial_call=True,
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
    prevent_initial_call=True,
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

    # Restore Screener's saved position and reset other research pages only on
    # a real tab transition. URL changes within an already-visible page also
    # refresh these style outputs; treating them as navigation would destroy the
    # user's reading position during portfolio selection or analysis routing.
    app.clientside_callback(
        """
        function(screener_style, analyze_style, portfolio_style, saved_pos) {
            var activeTab = screener_style && screener_style.display !== 'none'
                ? 'screener'
                : analyze_style && analyze_style.display !== 'none'
                ? 'analyze'
                : portfolio_style && portfolio_style.display !== 'none'
                ? 'portfolio'
                : null;
            var previousTab = window.__frVisibleResearchTab;
            window.__frVisibleResearchTab = activeTab;
            if (!activeTab || !previousTab || previousTab === activeTab) {
                return window.dash_clientside.no_update;
            }
            if (activeTab === 'screener') {
                requestAnimationFrame(function() {
                    window.scrollTo(0, saved_pos || 0);
                });
            } else {
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
