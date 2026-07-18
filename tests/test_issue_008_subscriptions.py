from __future__ import annotations

from unittest.mock import patch

from codes.payments import subscriptions
from codes.services.pricing import FREE, PREMIUM, plan_definition, plan_for_price_id


def test_plan_catalog_is_the_single_checkout_and_entitlement_source() -> None:
    assert plan_definition(PREMIUM)["stripe_price_env"] == "STRIPE_PREMIUM_PRICE_ID"
    assert plan_definition("retired") is None
    assert plan_for_price_id("price_unknown", {PREMIUM: "price_premium"}) == FREE
    assert plan_for_price_id("price_premium", {PREMIUM: "price_premium"}) == PREMIUM


def test_active_unknown_stripe_price_fails_closed_to_free(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_PREMIUM_PRICE_ID", "price_real")
    assert subscriptions.status_to_plan("active", "price_unknown") == FREE
    assert subscriptions.status_to_plan("active", "price_real") == PREMIUM


def test_known_payment_failure_does_not_change_to_premium_without_price() -> None:
    with patch.dict("os.environ", {"STRIPE_PREMIUM_PRICE_ID": "price_real"}, clear=False):
        assert subscriptions.status_to_plan("past_due", "price_unknown") == FREE
