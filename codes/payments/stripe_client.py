"""Thin Stripe API wrapper for subscription checkout and billing portal."""

from __future__ import annotations

import os

from codes.data import db


STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PREMIUM_PRICE_ID = os.environ.get("STRIPE_PREMIUM_PRICE_ID") or os.environ.get("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("APP_BASE_URL")


class StripeConfigurationError(RuntimeError):
    pass


def _stripe():
    if not STRIPE_SECRET_KEY:
        raise StripeConfigurationError("STRIPE_SECRET_KEY is not configured.")
    try:
        import stripe
    except ImportError as exc:
        raise StripeConfigurationError("The stripe Python package is not installed.") from exc
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def _base_url() -> str:
    if not PUBLIC_BASE_URL:
        raise StripeConfigurationError("PUBLIC_BASE_URL is required for Stripe redirects.")
    return PUBLIC_BASE_URL.rstrip("/")


def _price_id_for_plan(plan: str) -> str:
    plan = (plan or "premium").lower()
    if plan != "premium":
        raise StripeConfigurationError("Only the Premium plan is available.")
    if not STRIPE_PREMIUM_PRICE_ID:
        raise StripeConfigurationError("STRIPE_PREMIUM_PRICE_ID or STRIPE_PRICE_ID is not configured.")
    return STRIPE_PREMIUM_PRICE_ID


def is_configured() -> bool:
    return bool(STRIPE_SECRET_KEY and STRIPE_PREMIUM_PRICE_ID and PUBLIC_BASE_URL)


def create_checkout_session(user_id: str, plan: str = "premium") -> str:
    stripe = _stripe()
    price_id = _price_id_for_plan(plan)
    subscription = db.get_subscription(user_id) or {}
    params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "client_reference_id": user_id,
        "success_url": f"{_base_url()}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{_base_url()}/?billing=cancelled",
        "metadata": {"user_id": user_id, "plan": "premium"},
        "subscription_data": {"metadata": {"user_id": user_id, "plan": "premium"}},
        "allow_promotion_codes": True,
    }
    if subscription.get("stripe_customer_id"):
        params["customer"] = subscription["stripe_customer_id"]
    session = stripe.checkout.Session.create(**params)
    return session.url


def create_billing_portal_session(user_id: str) -> str:
    stripe = _stripe()
    subscription = db.get_subscription(user_id)
    customer_id = subscription.get("stripe_customer_id") if subscription else None
    if not customer_id:
        raise StripeConfigurationError("No Stripe customer is linked to this user.")
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{_base_url()}/",
    )
    return session.url


def construct_webhook_event(payload: bytes, signature: str | None):
    stripe = _stripe()
    if not STRIPE_WEBHOOK_SECRET:
        raise StripeConfigurationError("STRIPE_WEBHOOK_SECRET is not configured.")
    return stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
