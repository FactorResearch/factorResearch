import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.payments import subscriptions, webhooks
from codes.services import permissions
from codes.services.pricing import PLANS, normalize_plan


def test_pricing_has_only_free_and_premium_tiers():
    assert set(PLANS) == {"free", "premium"}
    assert PLANS["free"]["analysis_limit"] == 3
    assert "backtest" not in PLANS["free"]["features"]
    assert normalize_plan("trial") == "free"
    assert normalize_plan("professional") == "free"


def test_trial_analysis_limit_allows_three_then_locks():
    with patch("codes.services.permissions.db.get_subscription", return_value=None), \
         patch("codes.services.permissions.db.upsert_subscription",
               return_value={"plan": "trial", "status": "trialing"}), \
         patch("codes.services.permissions.db.get_total_usage", return_value=2):
        result = permissions.can_access_feature("u1", permissions.Feature.ANALYSIS)
        assert result.allowed is True
        assert result.remaining == 1

    with patch("codes.services.permissions.db.get_subscription", return_value=None), \
         patch("codes.services.permissions.db.upsert_subscription",
               return_value={"plan": "trial", "status": "trialing"}), \
         patch("codes.services.permissions.db.get_total_usage", return_value=3):
        result = permissions.can_access_feature("u1", permissions.Feature.ANALYSIS)
        assert result.allowed is False
        assert result.upgrade_required is True
        assert "3 free analyses" in result.message


def test_premium_subscription_unlocks_analysis_and_backtest():
    sub = {"plan": "premium", "status": "active"}
    with patch("codes.services.permissions.db.get_subscription", return_value=sub):
        assert permissions.can_access_feature("u1", permissions.Feature.ANALYSIS).allowed is True
        assert permissions.can_access_feature("u1", permissions.Feature.BACKTEST).allowed is True


def test_trial_custom_weights_allowed_but_backtest_locked():
    with patch("codes.services.permissions.db.get_subscription", return_value=None), \
         patch("codes.services.permissions.db.upsert_subscription",
               return_value={"plan": "trial", "status": "trialing"}):
        assert permissions.can_access_feature("u1", permissions.Feature.CUSTOM_WEIGHTS).allowed is True
        result = permissions.can_access_feature("u1", permissions.Feature.BACKTEST)
        assert result.allowed is False
        assert result.upgrade_required is True


def test_analysis_consumption_uses_atomic_limit_check():
    with patch("codes.services.permissions.db.get_subscription", return_value={"plan": "free", "status": "trialing"}), \
         patch("codes.services.permissions.db.get_total_usage", side_effect=[2, 3]), \
         patch("codes.services.permissions.db.consume_limited_usage", return_value={"usage_count": 3}) as consume:
        result = permissions.consume_analysis_if_allowed("u1", ticker="AAPL")

    assert result.allowed is True
    assert result.remaining == 0
    consume.assert_called_once_with("u1", "analysis", 3, usage_key="AAPL")


def test_checkout_completed_syncs_subscription_by_metadata_user_id():
    session = {
        "metadata": {"user_id": "u1", "plan": "premium"},
        "customer": "cus_123",
        "subscription": "sub_123",
    }
    with patch("codes.payments.subscriptions.db.upsert_subscription") as upsert:
        subscriptions.sync_checkout_completed(session)
    upsert.assert_called_once_with(
        "u1",
        plan="premium",
        status="active",
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
    )


def test_subscription_webhook_updates_status_from_stripe_payload():
    event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_123",
                "status": "canceled",
                "metadata": {"user_id": "u1"},
                "items": {"data": [{"price": {"id": "price_premium"}}]},
            }
        },
    }
    with patch("codes.payments.subscriptions.db.upsert_subscription") as upsert:
        handled = webhooks.handle_event(event)
    assert handled is True
    assert upsert.call_args.kwargs["plan"] == "cancelled"
    assert upsert.call_args.kwargs["status"] == "canceled"
