import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.app_modules import analysis as stock_analysis
from codes.app_modules.tabs import analyze, factor_lab, pricing, screener
from codes.data import analytics_db
from codes.payments import webhooks
from codes.services import product_analytics
from codes.services.permissions import Feature, PermissionResult


def test_track_event_updates_usage_and_persists_event(monkeypatch):
    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    usage = {"usage_count": 1, "feature_usage": {"source=test": 1}}
    increment = Mock(return_value=usage)
    insert = Mock()
    executor = Mock()
    executor.submit = lambda fn, *args: fn(*args)

    monkeypatch.setattr(product_analytics.db, "increment_usage", increment)
    monkeypatch.setattr(product_analytics.analytics_db, "insert_event", insert)
    monkeypatch.setattr(product_analytics, "_EXECUTOR", executor)

    with app.test_request_context("/pricing"):
        flask.session["_uid"] = "anon-1"
        result = product_analytics.track_event("user-1", "pricing_page_viewed", {"source": "test"})

    assert result == usage
    increment.assert_called_once()
    insert.assert_called_once()
    assert insert.call_args.kwargs["event_name"] == "pricing_page_viewed"
    assert insert.call_args.kwargs["page_path"] == "/pricing"


def test_pricing_tab_tracks_page_view(monkeypatch):
    tracked = Mock()
    monkeypatch.setattr(pricing.product_analytics, "track_event", tracked)
    monkeypatch.setattr(pricing, "get_user_id", lambda: "u1")

    pricing.render_pricing_tab({"source": "lock"})

    tracked.assert_called_once_with("u1", "pricing_page_viewed", {"source": "lock"})


def test_analyze_success_tracks_started_completed_and_stock_view(monkeypatch):
    monkeypatch.setattr(analyze, "check_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(analyze, "get_user_id", lambda: "u1")
    allow = PermissionResult(True, Feature.ANALYSIS, plan="trial", status="trialing", remaining=3)
    monkeypatch.setattr(analyze.permissions, "can_access_feature", lambda *_: allow)
    monkeypatch.setattr(analyze.permissions, "consume_analysis_if_allowed", lambda *args, **kwargs: allow)
    monkeypatch.setattr(
        analyze,
        "analyze_stock",
        lambda symbol: {"symbol": symbol, "name": "Apple", "cache_hit": True, "cache_source": "memory"},
    )
    monkeypatch.setattr(analyze, "_build_analysis_content", lambda result: ["content"])
    monkeypatch.setattr(analyze.screener, "update_stock_after_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(analyze.dash, "ctx", SimpleNamespace(triggered_id="analyze-btn"))
    tracked = Mock()
    monkeypatch.setattr(analyze.product_analytics, "track_event", tracked)

    analyze.run_analysis(1, None, "/", "AAPL", [])

    assert tracked.call_args_list[0].args[1] == "analysis_started"
    assert tracked.call_args_list[1].args[1] == "analysis_completed"
    assert tracked.call_args_list[1].args[2]["cache_hit"] is True
    assert tracked.call_args_list[1].args[2]["cache_source"] == "memory"
    assert tracked.call_args_list[1].args[2]["duration_ms"] >= 0
    assert tracked.call_args_list[2].args[1] == "stock_viewed"


def test_analyze_business_error_tracks_failure_class(monkeypatch):
    monkeypatch.setattr(analyze, "check_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(analyze, "get_user_id", lambda: "u1")
    allow = PermissionResult(True, Feature.ANALYSIS, plan="trial", status="trialing", remaining=3)
    monkeypatch.setattr(analyze.permissions, "can_access_feature", lambda *_: allow)
    monkeypatch.setattr(analyze, "analyze_stock", lambda symbol: {"error": "No data"})
    monkeypatch.setattr(analyze.dash, "ctx", SimpleNamespace(triggered_id="analyze-btn"))
    tracked = Mock()
    monkeypatch.setattr(analyze.product_analytics, "track_event", tracked)

    analyze.run_analysis(1, None, "/", "AAPL", [])

    failed = tracked.call_args_list[1]
    assert failed.args[1] == "analysis_failed"
    assert failed.args[2]["failure_class"] == "business_error"
    assert failed.args[2]["reason"] == "business_error"
    assert failed.args[2]["duration_ms"] >= 0


def test_factor_lab_tracks_backtest_started_and_completed(monkeypatch):
    monkeypatch.setattr(factor_lab, "check_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(factor_lab, "get_user_id", lambda: "u1")
    monkeypatch.setattr(factor_lab.product_analytics, "track_event", Mock())
    monkeypatch.setattr(factor_lab.permissions, "can_access_feature",
                        lambda *_: PermissionResult(True, Feature.BACKTEST, plan="premium", status="active"))
    monkeypatch.setattr(factor_lab.permissions, "record_feature_usage", lambda *args, **kwargs: None)

    from codes.engine import strategy_cache, user_strategy
    monkeypatch.setattr(user_strategy, "set_user_weights", lambda *args, **kwargs: None)
    monkeypatch.setattr(strategy_cache, "get_or_run_backtest", lambda **kwargs: {
        "custom": {"error": None}, "default": {"error": None}, "spy": {"error": None},
        "n_analysed": 10, "top_n": 10, "years": 5, "cache_hit": False,
        "weight_changes": [], "custom_top": [], "default_top": [], "ranked_stocks": [], "overlap": [],
    })
    monkeypatch.setattr(factor_lab, "_render_fb_results", lambda result: ["ok"])

    factor_lab.run_factor_backtest_cb(1, 10, 5, *([10] * 10))

    names = [call.args[1] for call in factor_lab.product_analytics.track_event.call_args_list]
    assert names == ["algorithm_selected", "backtest_started", "backtest_completed"]
    assert factor_lab.product_analytics.track_event.call_args_list[0].args[2]["algorithm"] == "custom_weights"
    assert factor_lab.product_analytics.track_event.call_args_list[2].args[2]["cache_hit"] is False
    assert factor_lab.product_analytics.track_event.call_args_list[2].args[2]["duration_ms"] >= 0


def test_factor_lab_business_error_tracks_failure_class(monkeypatch):
    monkeypatch.setattr(factor_lab, "check_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(factor_lab, "get_user_id", lambda: "u1")
    monkeypatch.setattr(factor_lab.product_analytics, "track_event", Mock())
    monkeypatch.setattr(factor_lab.permissions, "can_access_feature",
                        lambda *_: PermissionResult(True, Feature.BACKTEST, plan="premium", status="active"))

    from codes.engine import strategy_cache, user_strategy
    monkeypatch.setattr(user_strategy, "set_user_weights", lambda *args, **kwargs: None)
    monkeypatch.setattr(strategy_cache, "get_or_run_backtest", lambda **kwargs: {"error": "backtest failed"})

    factor_lab.run_factor_backtest_cb(1, 10, 5, *([10] * 10))

    failed = factor_lab.product_analytics.track_event.call_args_list[2]
    assert failed.args[1] == "backtest_failed"
    assert failed.args[2]["failure_class"] == "business_error"
    assert failed.args[2]["reason"] == "result_error"
    assert failed.args[2]["duration_ms"] >= 0


def test_factor_lab_default_weights_track_default_algorithm(monkeypatch):
    monkeypatch.setattr(factor_lab, "check_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(factor_lab, "get_user_id", lambda: "u1")
    monkeypatch.setattr(factor_lab.product_analytics, "track_event", Mock())
    monkeypatch.setattr(factor_lab.permissions, "can_access_feature",
                        lambda *_: PermissionResult(True, Feature.BACKTEST, plan="premium", status="active"))
    monkeypatch.setattr(factor_lab.permissions, "record_feature_usage", lambda *args, **kwargs: None)

    from codes.engine import strategy_cache, user_strategy
    monkeypatch.setattr(user_strategy, "set_user_weights", lambda *args, **kwargs: None)
    monkeypatch.setattr(strategy_cache, "get_or_run_backtest", lambda **kwargs: {
        "custom": {"error": None}, "default": {"error": None}, "spy": {"error": None},
        "n_analysed": 10, "top_n": 10, "years": 5, "cache_hit": False,
        "weight_changes": [], "custom_top": [], "default_top": [], "ranked_stocks": [], "overlap": [],
    })
    monkeypatch.setattr(factor_lab, "_render_fb_results", lambda result: ["ok"])

    weight_vals = [round(factor_lab.scorer.ENHANCED_WEIGHTS.get(k, 0) * 100) for k in factor_lab._FB_WEIGHT_KEYS]
    factor_lab.run_factor_backtest_cb(1, 10, 5, *weight_vals)

    first = factor_lab.product_analytics.track_event.call_args_list[0]
    assert first.args[1] == "algorithm_selected"
    assert first.args[2]["algorithm"] == "default_weights"


def test_analyze_stock_marks_cache_source(monkeypatch):
    monkeypatch.setattr(analytics_db, "ensure_schema", lambda: None)
    monkeypatch.setattr(stock_analysis.db, "get_analysis", lambda symbol: None)
    monkeypatch.setattr(stock_analysis.sec_data, "get_financials", lambda symbol: {"name": "Apple", "sector": "Technology"})
    monkeypatch.setattr(stock_analysis.quality, "score", lambda sec_facts: {"score": 1})
    monkeypatch.setattr(stock_analysis.api_fetcher, "get_price", lambda symbol: None)
    monkeypatch.setattr(stock_analysis.graham, "score", lambda price, sec_facts: {"market_cap": None})
    monkeypatch.setattr(stock_analysis.scorer, "composite", lambda *args, **kwargs: {"score": 1})
    monkeypatch.setattr(stock_analysis.piotroski, "score", lambda sec_facts: {})
    monkeypatch.setattr(stock_analysis.altman, "score", lambda price, sec_facts: {})
    monkeypatch.setattr(stock_analysis.greenblatt, "compute_single", lambda price, sec_facts: {})
    monkeypatch.setattr(stock_analysis.buffett, "score", lambda price, sec_facts: {})
    monkeypatch.setattr(stock_analysis.scorer, "enhanced_composite", lambda *args, **kwargs: {"composite_score": 1})
    monkeypatch.setattr(stock_analysis.scorer, "apply_regime_overlay", lambda *args, **kwargs: {})
    monkeypatch.setattr(stock_analysis.factor_engine, "persist_factor_scores", lambda *args, **kwargs: None)
    monkeypatch.setattr(stock_analysis.db, "upsert_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(stock_analysis, "save_standard_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(stock_analysis, "_get_market_fear_result", lambda: None)
    monkeypatch.setattr(stock_analysis, "_analysis_cache", {})

    fresh = stock_analysis.analyze_stock("AAPL")
    assert fresh["cache_hit"] is False
    assert fresh["cache_source"] == "fresh"

    from_db = {"symbol": "MSFT", "name": "Microsoft", "sector": "Technology"}
    monkeypatch.setattr(stock_analysis.db, "get_analysis", lambda symbol: from_db)
    cached_db = stock_analysis.analyze_stock("MSFT")
    assert cached_db["cache_hit"] is True
    assert cached_db["cache_source"] == "database"

    cached_memory = stock_analysis.analyze_stock("MSFT")
    assert cached_memory["cache_hit"] is True
    assert cached_memory["cache_source"] == "memory"


def test_webhook_tracks_subscription_completed(monkeypatch):
    tracked = Mock()
    monkeypatch.setattr(webhooks.product_analytics, "track_event", tracked)
    monkeypatch.setattr(webhooks.subscriptions, "sync_checkout_completed", lambda payload: payload)

    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"user_id": "u1", "plan": "premium"}}},
    }

    assert webhooks.handle_event(event) is True
    tracked.assert_called_once_with("u1", "subscription_completed", {"plan": "premium"})


def test_screener_tracks_screener_run(monkeypatch):
    screener.last_screener_state = None
    monkeypatch.setattr(screener.dash, "ctx", SimpleNamespace(triggered_id="sector-filter"))
    monkeypatch.setattr(screener, "get_user_id", lambda: "u1")
    monkeypatch.setattr(screener, "get_portfolio_symbols", lambda: {})
    monkeypatch.setattr(screener.screener, "get_progress", lambda: {"running": False, "total": 1, "done": 1})
    monkeypatch.setattr(screener.screener, "get_screener_results", lambda: [{
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "market_cap": 1000,
        "composite_score": 72,
        "graham_number": 180,
        "buffett_iv": 190,
        "updated_at": "2026-07-10",
        "verdict": "HIGH CONVICTION",
        "verdict_label": "strong-buy",
        "analyzed": True,
        "price": 170,
    }])
    tracked = Mock()
    monkeypatch.setattr(screener.product_analytics, "track_event", tracked)

    screener.render_screener_table(-1, "US", 1, "Technology", {"col": "composite_score", "asc": False}, 1, [])

    tracked.assert_called_once_with(
        "u1",
        "screener_run",
        {
            "country": "US",
            "sector": "Technology",
            "sort_col": "composite_score",
            "sort_asc": False,
            "result_count": 1,
        },
    )


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.row_factory = None
        self.last_sql = None
        self.last_params = None

    def execute(self, sql, params):
        self.last_sql = sql
        self.last_params = params
        return _FakeResult(self.rows)


def test_analytics_db_list_recent_events(monkeypatch):
    conn = _FakeConn([
        {
            "occurred_at": "2026-07-10T12:00:00Z",
            "user_id": "u1",
            "anonymous_id": "a1",
            "event_name": "stock_viewed",
            "page_path": "/analyze/AAPL",
            "metadata_json": {"symbol": "AAPL"},
        }
    ])

    class _Ctx:
        def __enter__(self):
            return conn

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(analytics_db, "ensure_schema", lambda: None)
    monkeypatch.setattr(analytics_db, "_conn", lambda: _Ctx())

    rows = analytics_db.list_recent_events(limit=5)

    assert rows[0]["event_name"] == "stock_viewed"
    assert conn.last_params == {"limit": 5}


def test_analytics_db_get_event_counts(monkeypatch):
    conn = _FakeConn([
        {"event_name": "stock_viewed", "event_count": 12},
        {"event_name": "analysis_completed", "event_count": 4},
    ])

    class _Ctx:
        def __enter__(self):
            return conn

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(analytics_db, "ensure_schema", lambda: None)
    monkeypatch.setattr(analytics_db, "_conn", lambda: _Ctx())

    rows = analytics_db.get_event_counts(limit=10)

    assert rows[0] == {"event_name": "stock_viewed", "event_count": 12}
    assert conn.last_params == {"limit": 10}


def test_analytics_db_get_top_metadata_values(monkeypatch):
    conn = _FakeConn([
        {"metadata_value": "AAPL", "event_count": 7},
        {"metadata_value": "MSFT", "event_count": 3},
    ])

    class _Ctx:
        def __enter__(self):
            return conn

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(analytics_db, "ensure_schema", lambda: None)
    monkeypatch.setattr(analytics_db, "_conn", lambda: _Ctx())

    rows = analytics_db.get_top_metadata_values("stock_viewed", "symbol", limit=8)

    assert rows[0] == {"metadata_value": "AAPL", "event_count": 7}
    assert conn.last_params == {"event_name": "stock_viewed", "metadata_key": "symbol", "limit": 8}
