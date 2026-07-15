"""Analyze tab callbacks."""

import re
import time as _time
import json

import dash
from dash import Input, Output, State, callback, clientside_callback
from dash.exceptions import PreventUpdate

from codes.engine import screener
from codes.data import db
from codes.app_modules.analysis import analyze_stock_primary as analyze_stock, _is_rate_limit_error
from codes.core.config import is_production
from codes.app_modules.analysis_ui import _build_analysis_content, build_analysis_charts
from codes.app_modules.rate_limit import RateLimited, check_rate_limit
from codes.app_modules.session import get_user_id
from codes.services import permissions
from codes.services import product_analytics
from codes.services import performance_metrics
from codes.services import analysis_demand
from codes.app_modules.components.feature_lock_modal import FeatureLockedModal
from codes.app_modules.components.upgrade_banner import UpgradeBanner
from codes.app_modules.tabs.pricing import open_upgrade_funnel


_ANALYZE_PATH_RE = re.compile(
    r"^(?:/analyze/([A-Za-z]{1,6})(?:/(?:\d{8}|\d{4}-\d{2}-\d{2}))?"
    r"|/([A-Za-z]{1,6})/analyze/(?:\d{8}|\d{4}-\d{2}-\d{2}))/?$"
)


def _client_analysis_payload(result: dict) -> dict:
    """Keep large chart histories server-side until the user opens Charts."""
    return {key: value for key, value in result.items() if key not in {"price_history", "spy_history"}}


clientside_callback(
    """
    function(children, hash, tabStyle) {
        window.requestAnimationFrame(function() {
            var links = Array.from(document.querySelectorAll('.analysis-jump-link'));
            var sections = links.map(function(link) {
                return document.getElementById(link.getAttribute('href').slice(1));
            }).filter(Boolean);
            if (window.factorResearchScrollHandler) {
                window.removeEventListener('scroll', window.factorResearchScrollHandler);
            }
            var ticking = false;
            function updateActiveSection() {
                ticking = false;
                var marker = 150;
                var active = sections[0];
                sections.forEach(function(section) {
                    if (section.getBoundingClientRect().top <= marker) active = section;
                });
                if (!active) return;
                links.forEach(function(link) {
                    var isActive = link.getAttribute('href') === '#' + active.id;
                    link.classList.toggle('active', isActive);
                    if (isActive) link.setAttribute('aria-current', 'true');
                    else link.removeAttribute('aria-current');
                });
            }
            links.forEach(function(link) {
                link.onclick = function(event) {
                    event.preventDefault();
                    var target = document.getElementById(link.getAttribute('href').slice(1));
                    if (!target) return;
                    target.scrollIntoView({behavior: 'smooth', block: 'start'});
                    window.history.replaceState(null, '', link.getAttribute('href'));
                    window.requestAnimationFrame(updateActiveSection);
                };
            });
            window.factorResearchScrollHandler = function() {
                if (ticking) return;
                ticking = true;
                window.requestAnimationFrame(updateActiveSection);
            };
            window.addEventListener('scroll', window.factorResearchScrollHandler, {passive: true});
            updateActiveSection();
        });
        if (!hash || hash.length < 2) {
            return window.dash_clientside.no_update;
        }
        if (tabStyle && tabStyle.display === 'none') {
            return window.dash_clientside.no_update;
        }

        var id = hash.slice(1);
        try {
            id = decodeURIComponent(id);
        } catch (e) {}
        var attempts = 0;

        function findTarget() {
            if (window.CSS && CSS.escape) {
                return document.querySelector('#' + CSS.escape(id));
            }
            return document.getElementById(id);
        }

        function scrollWhenReady() {
            var target = findTarget();
            if (target) {
                target.scrollIntoView({ behavior: 'auto', block: 'start' });
                return;
            }
            attempts += 1;
            if (attempts < 20) {
                window.setTimeout(scrollWhenReady, 100);
            }
        }

        window.requestAnimationFrame(function() {
            window.setTimeout(scrollWhenReady, 0);
        });
        return hash;
    }
    """,
    Output("analysis-anchor-scroll-trigger", "children"),
    Input("analysis-content", "children"),
    Input("url", "hash"),
    Input("tab-analyze", "style"),
    prevent_initial_call=False,
)


def _ticker_from_analyze_path(pathname: str | None) -> str | None:
    match = _ANALYZE_PATH_RE.fullmatch(pathname or "")
    if not match:
        return None
    return (match.group(1) or match.group(2)).upper()


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
    Output("upgrade-funnel-store",    "data"),
    Input("analyze-btn",          "n_clicks"),
    Input("screener-open-analysis-symbol","data"),
    Input("url",                  "pathname"),
    State("ticker-input",         "value"),
    State("screener-viewed-store","data"),
    prevent_initial_call=False
)
def run_analysis(n_clicks, open_analysis_symbol, pathname, ticker_input_value, viewed_list):
    """
    Single callback: fetch + score + render.
    Because analysis-content is a child of dcc.Loading(id='analysis-loading'),
    Dash shows the spinner for the entire duration of this callback.
    """
    triggered = dash.ctx.triggered_id
    route_ticker = _ticker_from_analyze_path(pathname)
    if triggered == "screener-open-analysis-symbol" and open_analysis_symbol:
        ticker = open_analysis_symbol
    elif route_ticker and (triggered in ("url", None) or not ticker_input_value):
        ticker = route_ticker
    else:
        ticker = ticker_input_value
    if triggered in ("url", None) and not route_ticker:
        raise PreventUpdate
    if not ticker or not ticker.strip():
        return dash.no_update, [], None, "❌ Please enter a ticker symbol.", False, False, dash.no_update, {"display": "none"}, None, dash.no_update, dash.no_update
    symbol = ticker.strip().upper()
    # Input validation: ticker must be 1-6 uppercase letters
    if not re.fullmatch(r"^[A-Z]{1,6}$", symbol):
        return dash.no_update, [], None, "❌ Invalid ticker format. Use 1–6 uppercase letters (A–Z).", False, False, dash.no_update, {"display": "none"}, None, dash.no_update, dash.no_update
    # Rate limit (per-user) — max 10 analyze calls per minute
    try:
        check_rate_limit("analyze", calls=10, period_seconds=60)
    except RateLimited as rl:
        return dash.no_update, [], None, f"⏳ Rate limit exceeded — try again in {rl.retry_after}s.", False, False, dash.no_update, {"display": "none"}, None, dash.no_update, dash.no_update
    user_id = get_user_id()
    try:
        access = permissions.can_access_feature(user_id, permissions.Feature.ANALYSIS)
        if not access.allowed:
            product_analytics.track_event(
                user_id,
                "upgrade_viewed",
                {"feature": "analysis", "source": "analyze_lock", "plan": "premium"},
            )
            return (
                "/pricing",
                [FeatureLockedModal(feature="analysis", source="analyze_lock")],
                None,
                "🔒 Upgrade required to continue.",
                False,
                False,
                dash.no_update,
                {"display": "none"},
                None,
                dash.no_update,
                open_upgrade_funnel(
                    feature="analysis",
                    feature_label="Company analysis",
                    reason=access.message,
                    source="analyze_lock",
                ),
            )
    except Exception:
        if is_production():
            return dash.no_update, [], None, "🔒 Billing unavailable — please try later.", False, False, dash.no_update, {"display": "none"}, None, dash.no_update, dash.no_update
        access = None
    product_analytics.track_event(user_id, "analysis_started", {"symbol": symbol, "source": triggered or "direct"})
    started_at = _time.perf_counter()
    try:
        result = analyze_stock(symbol)
    except Exception as e:
        duration_ms = int((_time.perf_counter() - started_at) * 1000)
        if _is_rate_limit_error(e):
            message = getattr(e, "user_message", str(e))
            product_analytics.track_event(
                user_id,
                "analysis_failed",
                {
                    "symbol": symbol,
                    "failure_class": "rate_limit",
                    "reason": "rate_limit",
                    "duration_ms": duration_ms,
                },
            )
            return dash.no_update, [], None, f"❌ {message}", False, False, symbol, {"display": "none"}, None, dash.no_update, dash.no_update
        print(f"run_analysis unexpected error: {type(e).__name__}: {e}")
        product_analytics.track_event(
            user_id,
            "analysis_failed",
            {
                "symbol": symbol,
                "failure_class": "exception",
                "reason": type(e).__name__,
                "duration_ms": duration_ms,
            },
        )
        return dash.no_update, [], None, "❌ Internal server error — please try again later.", False, False, dash.no_update, {"display": "none"}, None, dash.no_update, dash.no_update
    if "error" in result:
        duration_ms = int((_time.perf_counter() - started_at) * 1000)
        product_analytics.track_event(
            user_id,
            "analysis_failed",
            {
                "symbol": symbol,
                "failure_class": "business_error",
                "reason": "business_error",
                "duration_ms": duration_ms,
            },
        )
        return dash.no_update, [], None, f"❌ {result['error']}", False, False, symbol, {"display": "none"}, None, dash.no_update, dash.no_update
    duration_ms = int((_time.perf_counter() - started_at) * 1000)
    product_analytics.track_event(
        user_id,
        "analysis_completed",
        {
            "symbol": symbol,
            "source": triggered or "direct",
            "duration_ms": duration_ms,
            "cache_hit": bool(result.get("cache_hit")),
            "cache_source": result.get("cache_source", "unknown"),
        },
    )
    product_analytics.track_event(user_id, "stock_viewed", {"symbol": symbol, "source": "analysis"})
    analysis_demand.record(symbol)
    viewed_updated = list(set((viewed_list or []) + [symbol]))
    content = _build_analysis_content(result)
    # Update screener row with full analysis data (Graham Number, live price, enhanced score)
    screener.update_stock_after_analysis(symbol, result)
    usage_msg = ""
    if access and access.remaining is not None:
        consumed = permissions.consume_analysis_if_allowed(user_id, ticker=symbol)
        usage_msg = f" · {consumed.remaining} free analyses remaining"
        content = [UpgradeBanner(remaining=consumed.remaining), *content]
    client_result = _client_analysis_payload(result)
    performance_metrics.record_payload(len(json.dumps(client_result, default=str)))
    return (
        dash.no_update if triggered in ("url", None) else f"/{symbol}/analyze/{_time.strftime('%Y%m%d')}",
        content,
        client_result,
        f"✅ {result['name']} ({symbol}) — Analysis complete{usage_msg}",
        False, False, symbol,
        {"display": "block"},
        symbol,
        viewed_updated,
        dash.no_update,
    )


@callback(
    Output("analysis-charts-content", "children"),
    Input("analysis-charts-summary", "n_clicks"),
    State("analysis-store", "data"),
    prevent_initial_call=True,
)
def render_analysis_charts_on_demand(n_clicks, analysis):
    if not n_clicks or not analysis:
        return dash.no_update
    chart_analysis = analysis
    if not analysis.get("price_history"):
        chart_analysis = db.get_analysis(analysis.get("symbol", "")) or analysis
    return build_analysis_charts(chart_analysis)


@callback(
    Output("analysis-content", "children", allow_duplicate=True),
    Output("analysis-store", "data", allow_duplicate=True),
    Input("analysis-secondary-interval", "n_intervals"),
    State("analysis-store", "data"),
    prevent_initial_call=True,
)
def refresh_secondary_analysis(_n_intervals, analysis):
    if not analysis or analysis.get("secondary_status") != "pending":
        raise PreventUpdate
    enriched = db.get_analysis(analysis.get("symbol", ""))
    if not enriched or enriched.get("secondary_status") not in {"complete", "failed"}:
        raise PreventUpdate

    content = _build_analysis_content(enriched)
    access = permissions.can_access_feature(get_user_id(), permissions.Feature.ANALYSIS)
    if access and access.remaining is not None:
        content = [UpgradeBanner(remaining=access.remaining), *content]
    client_result = _client_analysis_payload(enriched)
    performance_metrics.record_payload(len(json.dumps(client_result, default=str)))
    return content, client_result


clientside_callback(
    """
    function(children) {
        function resizeCharts() {
            if (!window.Plotly) return;
            document.querySelectorAll('#analysis-charts-content .js-plotly-plot')
                .forEach(function(graph) { window.Plotly.Plots.resize(graph); });
        }
        window.requestAnimationFrame(function() {
            resizeCharts();
            window.setTimeout(resizeCharts, 120);
            window.setTimeout(resizeCharts, 350);
        });
        return Date.now();
    }
    """,
    Output("analysis-chart-resize-trigger", "children"),
    Input("analysis-charts-content", "children"),
    prevent_initial_call=True,
)
