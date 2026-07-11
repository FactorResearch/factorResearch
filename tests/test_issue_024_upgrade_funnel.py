from unittest.mock import Mock, patch
from types import SimpleNamespace

import flask

from codes import billing
from codes.app_modules.tabs import analyze, factor_lab, navigation
from codes.services.permissions import Feature, PermissionResult
from codes.services import permissions
from codes.app_modules.components.feature_lock_modal import FeatureLockedModal
from codes.app_modules.components.upgrade_banner import UpgradeBanner


def test_reusable_upgrade_components_use_required_copy():
    modal = FeatureLockedModal(feature="backtest", source="test")
    banner = UpgradeBanner(remaining=1)

    assert "Does your strategy actually work?" in str(modal)
    assert "Test your strategy using historical data" in str(modal)
    assert "Unlock Premium" in str(modal)
    assert "2/3 free analyses used" in str(banner)


def test_free_portfolio_analytics_is_locked(monkeypatch):
    monkeypatch.setattr(permissions.db, "get_subscription", lambda *_: None)
    monkeypatch.setattr(
        permissions.db,
        "upsert_subscription",
        lambda *args, **kwargs: {"plan": "trial", "status": "trialing"},
    )
    deny = permissions.can_access_feature("u1", Feature.PORTFOLIO_ANALYTICS)
    assert deny.allowed is False
    assert "requires Premium" in deny.message


def test_billing_entry_url_routes_through_checkout():
    url = billing.get_billing_entry_url(plan="premium", source="analyze_lock", feature="analysis")
    assert url.startswith("/billing/checkout?")
    assert "source=analyze_lock" in url
    assert "feature=analysis" in url


def test_navigation_switches_to_pricing_when_upgrade_store_is_set():
    with patch.object(navigation.dash, "ctx", SimpleNamespace(triggered_id="upgrade-funnel-store")):
        result = navigation.switch_tabs(0, 0, 0, 0, 0, None, {"feature": "analysis"}, "/")
    assert result[4] == {"display": "block"}
    assert result[-1] == "topbar-nav-btn tab-btn active"


def test_analyze_lock_routes_user_to_pricing(monkeypatch):
    deny = PermissionResult(False, Feature.ANALYSIS, reason="limit hit", upgrade_required=True)
    monkeypatch.setattr(analyze, "check_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(analyze, "get_user_id", lambda: "trial-user")
    monkeypatch.setattr(analyze.permissions, "can_access_feature", lambda *_: deny)
    tracked = Mock()
    monkeypatch.setattr(analyze.product_analytics, "track_event", tracked)
    monkeypatch.setattr(analyze.dash, "ctx", SimpleNamespace(triggered_id="analyze-btn"))

    result = analyze.run_analysis(1, None, "/", "AAPL", [])

    assert result[0] == "/pricing"
    assert result[3] == "🔒 Upgrade required to continue."
    assert result[-1]["feature"] == "analysis"
    tracked.assert_called_once()


def test_factor_lab_lock_sets_upgrade_store(monkeypatch):
    deny = PermissionResult(False, Feature.BACKTEST, reason="premium only", upgrade_required=True)
    monkeypatch.setattr(factor_lab, "check_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(factor_lab, "get_user_id", lambda: "trial-user")
    monkeypatch.setattr(factor_lab.permissions, "can_access_feature", lambda *_: deny)
    tracked = Mock()
    monkeypatch.setattr(factor_lab.product_analytics, "track_event", tracked)
    from codes.engine import user_strategy
    monkeypatch.setattr(user_strategy, "set_user_weights", lambda *args, **kwargs: None)

    result = factor_lab.run_factor_backtest_cb(1, 10, 5, *([10] * 10))

    assert result[1] == "🔒 Premium required"
    assert result[2]["feature"] == "backtest"
    tracked.assert_called_once()


def test_billing_checkout_tracks_funnel_events(monkeypatch):
    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    monkeypatch.setenv("FLASK_ENV", "development")
    billing.init_billing(app)
    tracked = Mock()
    monkeypatch.setattr(billing.product_analytics, "track_event", tracked)
    monkeypatch.setattr(billing, "get_checkout_url", lambda user_id, plan="premium": f"/checkout/{user_id}/{plan}")
    client = app.test_client()
    with client.session_transaction() as session:
        session["_uid"] = "current_user"

    response = client.get("/billing/checkout?plan=professional&source=pricing_tab&feature=subscription")

    assert response.status_code == 302
    assert response.headers["Location"] == "/checkout/current_user/professional"
    assert tracked.call_count == 2
