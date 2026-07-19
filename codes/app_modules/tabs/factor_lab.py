"""Factor Lab tab callbacks."""

import json
import time as _time
from math import isclose

import dash
from dash import Input, Output, State, callback, dcc, html

from codes.app_modules.analysis_ui import _chart_layout
from codes.app_modules.components.feature_lock_modal import FeatureLockedModal
from codes.app_modules.config import AMBER, BLUE, GREEN, MUTED, RED, TEXT
from codes.app_modules.css_classes import tone_class
from codes.app_modules.design_system.financial import data_trust_panel
from codes.app_modules.design_system.primitives import empty_state, table
from codes.app_modules.design_system.states import background_job_status, section_error
from codes.app_modules.rate_limit import RateLimited, check_rate_limit
from codes.app_modules.session import get_user_id
from codes.app_modules.tabs.pricing import open_upgrade_funnel
from codes.engine import scorer
from codes.services import performance_metrics, permissions, product_analytics
from codes.services.adaptive_loading import AsyncStatus, jobs

# ── Factor Lab callbacks ─────────────────────────────────────────────────────

_FB_WEIGHT_KEYS = [
    "graham", "quality", "momentum", "profitability", "fcf_quality",
    "earnings_revision", "capital_allocation", "growth_quality", "risk", "altman"
]


def _strategy_variant(custom_weights: dict[str, float]) -> str:
    total = sum(max(0.0, float(custom_weights.get(key, 0.0))) for key in _FB_WEIGHT_KEYS)
    for key in _FB_WEIGHT_KEYS:
        default_val = float(scorer.ENHANCED_WEIGHTS.get(key, 0.0))
        current_raw = max(0.0, float(custom_weights.get(key, 0.0)))
        current_val = (current_raw / total) if total > 0 else 0.0
        if not isclose(default_val, current_val, rel_tol=0, abs_tol=1e-9):
            return "custom_weights"
    return "default_weights"


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
    *[Output(f"fb-w-{key}", "value") for key in _FB_WEIGHT_KEYS],
    Input("fb-reset-weights-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_factor_weights(n_clicks):
    if not n_clicks:
        return tuple(dash.no_update for _ in _FB_WEIGHT_KEYS)
    return tuple(round(scorer.ENHANCED_WEIGHTS.get(key, 0) * 100) for key in _FB_WEIGHT_KEYS)


def run_factor_backtest_cb(n_clicks, top_n, years, *weight_vals, _uid=None, _skip_guards=False):
    """Execute a backtest; the UI submits this helper as a resumable job."""
    if not n_clicks:
        return [], "", None
    if not _skip_guards:
        try:
            check_rate_limit("backtest", calls=30, period_seconds=60, cost=10, priority="optional")
        except RateLimited as rl:
            return [section_error(f"Backtest rate limited. Try again in {rl.retry_after}s.")], "⏳ Rate limited", None

    from codes.engine import strategy_cache, user_strategy

    custom_weights = dict(zip(_FB_WEIGHT_KEYS, (v or 0 for v in weight_vals), strict=True))

    # Layer 3: persist this user's weight config
    uid = _uid or get_user_id()
    user_strategy.set_user_weights(uid, custom_weights)
    if not _skip_guards:
        try:
            access = permissions.can_access_feature(uid, permissions.Feature.BACKTEST)
            if not access.allowed:
                product_analytics.track_event(
                    uid,
                    "upgrade_viewed",
                    {"feature": "backtest", "source": "factor_lab_lock", "plan": "premium"},
                )
                return [FeatureLockedModal(feature="backtest", source="factor_lab_lock")], "🔒 Premium required", open_upgrade_funnel(
                    feature="backtest",
                    feature_label="Historical backtesting",
                    reason=access.message,
                    source="factor_lab_lock",
                )
        except Exception:
            return [section_error("Billing is unavailable. Please try again later.")], "🔒 Billing unavailable", None

    # Layer 4: cache-aware backtest, reused across identical configs
    product_analytics.track_event(
        uid,
        "algorithm_selected",
        {"source": "factor_lab", "algorithm": _strategy_variant(custom_weights)},
    )
    product_analytics.track_event(uid, "backtest_started", {"source": "factor_lab", "top_n": top_n or 10, "years": years or 5})
    started_at = _time.perf_counter()
    try:
        result = strategy_cache.get_or_run_backtest(
            weights=custom_weights,
            top_n=top_n or 10,
            years=years or 5,
        )
    except Exception as e:
        duration_ms = (_time.perf_counter() - started_at) * 1000
        performance_metrics.record_ui_operation(
            "factor-backtest", duration_ms, outcome="error", section="factor-results"
        )
        product_analytics.track_event(
            uid,
            "backtest_failed",
            {
                "source": "factor_lab",
                "failure_class": "exception",
                "reason": type(e).__name__,
                "duration_ms": int((_time.perf_counter() - started_at) * 1000),
            },
        )
        return [section_error("The backtest could not be completed.", technical_id=type(e).__name__)], "❌ Error", None

    if result.get("error"):
        duration_ms = (_time.perf_counter() - started_at) * 1000
        performance_metrics.record_ui_operation(
            "factor-backtest", duration_ms, outcome="error", section="factor-results"
        )
        product_analytics.track_event(
            uid,
            "backtest_failed",
            {
                "source": "factor_lab",
                "failure_class": "business_error",
                "reason": "result_error",
                "duration_ms": int((_time.perf_counter() - started_at) * 1000),
            },
        )
        return [section_error(str(result["error"]))], "❌ Error", None

    permissions.record_feature_usage(uid, permissions.Feature.BACKTEST)
    product_analytics.track_event(
        uid,
        "backtest_completed",
        {
            "source": "factor_lab",
            "top_n": result["top_n"],
            "years": result["years"],
            "duration_ms": int((_time.perf_counter() - started_at) * 1000),
            "cache_hit": bool(result.get("cache_hit")),
        },
    )
    cache_note = " (cached)" if result.get("cache_hit") else ""
    duration_ms = (_time.perf_counter() - started_at) * 1000
    performance_metrics.record_ui_operation(
        "factor-backtest",
        duration_ms,
        section="factor-results",
        first_useful_ms=duration_ms,
    )
    return _render_fb_results(result), (
        f"✅ {result['n_analysed']} stocks scored · "
        f"top {result['top_n']} selected · "
        f"{result['years']}yr backtest{cache_note}"
    ), None


@callback(
    Output("fb-results", "children"),
    Output("fb-status", "children"),
    Output("factor-job-store", "data"),
    Output("upgrade-funnel-store", "data", allow_duplicate=True),
    Output("factor-job-cancel", "style"),
    Input("fb-run-btn", "n_clicks"),
    State("fb-top-n", "value"),
    State("fb-years", "value"),
    *[State(f"fb-w-{k}", "value") for k in _FB_WEIGHT_KEYS],
    prevent_initial_call=True,
)
def start_factor_backtest_job(n_clicks, top_n, years, *weight_vals):
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    uid = get_user_id()
    try:
        access = permissions.can_access_feature(uid, permissions.Feature.BACKTEST)
    except Exception:
        return section_error("Billing is temporarily unavailable."), "Billing unavailable", dash.no_update, None, {"display": "none"}
    if not access.allowed:
        result, status, upgrade = run_factor_backtest_cb(n_clicks, top_n, years, *weight_vals)
        return result, status, dash.no_update, upgrade, {"display": "none"}
    try:
            check_rate_limit("backtest", calls=30, period_seconds=60, cost=10, priority="optional")
    except RateLimited as rl:
        return section_error(f"Backtest rate limited. Try again in {rl.retry_after}s."), "Rate limited", dash.no_update, None, {"display": "none"}

    weights = dict(zip(_FB_WEIGHT_KEYS, (value or 0 for value in weight_vals), strict=True))
    dedupe_key = json.dumps(
        {"weights": weights, "top_n": top_n or 10, "years": years or 5},
        sort_keys=True,
    )

    def work(context):
        context.update("Scoring available companies", completed_units=1)
        context.raise_if_cancelled()
        result = run_factor_backtest_cb(
            1, top_n, years, *weight_vals, _uid=uid, _skip_guards=True
        )
        context.update("Comparing strategy paths", completed_units=2)
        return result

    snapshot = jobs.submit(
        operation="factor-backtest",
        owner=uid,
        dedupe_key=dedupe_key,
        work=work,
        total_units=2,
    )
    return (
        background_job_status(snapshot.public_dict()),
        snapshot.stage,
        snapshot.public_dict(),
        None,
        {"display": "inline-flex"},
    )


@callback(
    Output("fb-results", "children", allow_duplicate=True),
    Output("fb-status", "children", allow_duplicate=True),
    Output("factor-job-store", "data", allow_duplicate=True),
    Output("upgrade-funnel-store", "data", allow_duplicate=True),
    Output("factor-job-cancel", "style", allow_duplicate=True),
    Input("factor-job-interval", "n_intervals"),
    Input("factor-job-cancel", "n_clicks"),
    State("factor-job-store", "data"),
    prevent_initial_call=True,
)
def poll_factor_backtest_job(_tick, cancel_clicks, stored):
    if not stored or not stored.get("job_id"):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    uid = get_user_id()
    job_id = stored["job_id"]
    if dash.ctx.triggered_id == "factor-job-cancel" and cancel_clicks:
        jobs.cancel(job_id, owner=uid)
    snapshot = jobs.snapshot(job_id, owner=uid)
    if snapshot is None:
        return section_error("This backtest is no longer available."), "Unavailable", None, None, {"display": "none"}
    public = snapshot.public_dict()
    if snapshot.status == AsyncStatus.SUCCESS:
        result = jobs.result(job_id, owner=uid)
        if result is not None:
            return result[0], result[1], public, result[2], {"display": "none"}
    if snapshot.status == AsyncStatus.ERROR:
        return section_error("The backtest failed. Retrying does not change your saved weights.", technical_id=snapshot.error_code), "Failed", public, None, {"display": "none"}
    if snapshot.status == AsyncStatus.CANCELLED:
        return empty_state("Backtest cancelled", "Your factor weights remain saved."), "Cancelled", public, None, {"display": "none"}
    return background_job_status(public), snapshot.stage, public, None, {"display": "inline-flex"}


@callback(
    Output("factor-job-interval", "disabled"),
    Input("factor-job-store", "data"),
    prevent_initial_call=False,
)
def sync_factor_job_polling(stored):
    """Poll only while a Factor Lab job is active."""
    if not stored or not stored.get("job_id"):
        return True
    return stored.get("status") in {"success", "error", "cancelled"}


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
            html.Td(label, className="clr-muted fs-12"),
            html.Td(_fmt(cv, fmt, sfx),
                    className=f"fw-700 fs-13 {tone_class(_cell_color(cv, dv))}"),
            html.Td(_fmt(dv, fmt, sfx), className="fs-13"),
            html.Td(_fmt(sv, fmt, sfx), className="fs-13 clr-muted"),
        ]))

    summary = html.Div(className="scorecard mt-20", children=[
        html.Div("📊 Performance Comparison", className="scorecard-header"),
        html.Div(
            "Green = custom beats default. Equal-weight buy-and-hold on stocks in your analysis cache.",
            className="factor-lab-summary-note fs-12 clr-muted fsi",
        ),
        table(className="screener-table", caption="Backtest performance comparison", children=[
            html.Thead(html.Tr([
                html.Th("Metric"),
                html.Th("Custom Weights", className="clr-blue"),
                html.Th("Default Weights"),
                html.Th("SPY", className="clr-muted"),
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
        chart = dcc.Graph(
            figure=fig,
            config={"displayModeBar": False, "responsive": True, "scrollZoom": False},
            className="responsive-financial-chart",
        )

    wc_rows = []
    for wc in r.get("weight_changes", []):
        delta = wc["delta"]
        d_color = GREEN if delta > 1 else RED if delta < -1 else MUTED
        wc_rows.append(html.Tr([
            html.Td(wc["factor"].replace("_", " ").title(), className="fs-12"),
            html.Td(f"{wc['custom']:.1f}%",
                    className="fw-700 clr-blue fs-13"),
            html.Td(f"{wc['default']:.1f}%", className="fs-12 clr-muted"),
            html.Td(f"{delta:+.1f}pp",
                    className=f"fw-600 fs-12 {tone_class(d_color)}"),
        ]))

    weight_table = html.Div(className="scorecard mt-16", children=[
        html.Div("⚖️ Weight Changes vs Default", className="scorecard-header"),
        table(className="screener-table", caption="Custom and default factor weights", children=[
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
            html.Td(s["name"][:22], className="fs-11 clr-muted"),
            html.Td(f"{s['custom_score']:.1f}",
                    className="fw-700 clr-blue"),
            html.Td(f"{s['default_score']:.1f}"),
            html.Td(f"{delta:+.1f}", className=f"fw-600 {tone_class(d_color)}"),
            html.Td("✅" if sym in custom_set  else "—", className="tac"),
            html.Td("✅" if sym in default_set else "—", className="tac"),
        ]))

    overlap = r.get("overlap", [])
    stocks_table = html.Div(className="scorecard mt-16", children=[
        html.Div(
            f"🏆 Stock Rankings — Custom top-{r['top_n']}: "
            f"{', '.join(r['custom_top'][:6])}{'...' if len(r['custom_top']) > 6 else ''}",
            className="scorecard-header",
        ),
        html.Div(
            f"Portfolio overlap: {len(overlap)}/{r['top_n']} stocks in both — "
            f"{', '.join(overlap) if overlap else 'none in common'}",
            className="factor-lab-overlap-note fs-12 clr-muted fsi",
        ),
        table(className="screener-table", caption="Custom and default stock rankings", children=[
            html.Thead(html.Tr([
                html.Th("Ticker"), html.Th("Name"),
                html.Th("Custom Score", className="clr-blue"),
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
                                   className="factor-lab-warning clr-amber fs-12"))

    trust = data_trust_panel({
        "provenance": {
            "analysis_date": r.get("generated_at"),
            "price_timestamp": "Historical period-end prices used by the backtest",
            "filing_period": f"Historical {r.get('years', 'selected')}-year test window",
            "source_category": "Cached company analyses and historical market observations",
            "currency": "USD indexed comparison",
            "normalization_status": "Series indexed to 100 at the test start",
            "calculation_status": "Historical backtest",
            "model_scope": "User-customized factor weights",
            "historical": True,
            "custom_model": True,
            "missing_effects": [
                "Backtests use the available historical universe and do not predict future performance."
            ],
        },
    }, compact=True)
    return [trust, summary, chart, weight_table, stocks_table] + warns
