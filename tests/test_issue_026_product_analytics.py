import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.app_modules.tabs import analyze, factor_lab, pricing
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
    monkeypatch.setattr(analyze, "analyze_stock", lambda symbol: {"symbol": symbol, "name": "Apple"})
    monkeypatch.setattr(analyze, "_build_analysis_content", lambda result: ["content"])
    monkeypatch.setattr(analyze.screener, "update_stock_after_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(analyze.dash, "ctx", SimpleNamespace(triggered_id="analyze-btn"))
    tracked = Mock()
    monkeypatch.setattr(analyze.product_analytics, "track_event", tracked)

    analyze.run_analysis(1, None, "/", "AAPL", [])

    assert tracked.call_args_list[0].args[1] == "analysis_started"
    assert tracked.call_args_list[1].args[1] == "analysis_completed"
    assert tracked.call_args_list[2].args[1] == "stock_viewed"


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
    assert names == ["backtest_started", "backtest_completed"]


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
