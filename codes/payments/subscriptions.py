"""Subscription state transitions for Stripe and local development."""

from __future__ import annotations

import datetime as _dt
import os
from typing import Any

from codes.core.config import is_production
from codes.data import db
from codes.services import pricing

STRIPE_ACTIVE_STATUSES = {"active", "trialing", "past_due"}
STRIPE_CANCELLED_STATUSES = {"canceled", "unpaid", "incomplete_expired"}


def _from_unix(ts: int | None):
    if not ts:
        return None
    return _dt.datetime.fromtimestamp(int(ts), tz=_dt.UTC)


def plan_from_price_id(price_id: str | None) -> str:
    # Keep the deterministic fixture identifier usable when Stripe settings
    # are intentionally absent in local tests; production requires a configured
    # price ID before checkout can be enabled.
    configured_price_id = os.environ.get("STRIPE_PREMIUM_PRICE_ID") or os.environ.get(
        "STRIPE_PRICE_ID"
    )
    if configured_price_id == "price_your_premium_price_id_here":
        configured_price_id = None
    if price_id == "price_premium" and not is_production() and not configured_price_id:
        return pricing.PREMIUM
    return pricing.plan_for_price_id(
        price_id,
        {pricing.PREMIUM: configured_price_id},
    )


def status_to_plan(status: str, price_id: str | None = None) -> str:
    status = (status or "").lower()
    return (
        pricing.PREMIUM
        if status in STRIPE_ACTIVE_STATUSES and plan_from_price_id(price_id) == pricing.PREMIUM
        else pricing.FREE
    )


def sync_checkout_completed(session: dict[str, Any]) -> dict | None:
    metadata = session.get("metadata") or {}
    user_id = metadata.get("user_id") or session.get("client_reference_id")
    if not user_id:
        return None
    stripe_customer_id = session.get("customer")
    stripe_subscription_id = session.get("subscription")
    return db.upsert_subscription(
        user_id,
        plan="premium",
        status="active",
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        privileged=True,
    )


def sync_subscription(subscription: dict[str, Any]) -> dict | None:
    stripe_subscription_id = subscription.get("id")
    stripe_customer_id = subscription.get("customer")
    metadata = subscription.get("metadata") or {}

    user_id = metadata.get("user_id")
    existing = None
    if not user_id and stripe_subscription_id:
        existing = db.get_subscription_by_stripe_id(stripe_subscription_id)
        user_id = existing.get("user_id") if existing else None
    if not user_id and stripe_customer_id:
        existing = db.get_subscription_by_customer(stripe_customer_id)
        user_id = existing.get("user_id") if existing else None
    if not user_id:
        return None

    price_id = None
    items = subscription.get("items") or {}
    data = items.get("data") or []
    if data:
        price = data[0].get("price") or {}
        price_id = price.get("id")

    status = subscription.get("status") or "incomplete"
    return db.upsert_subscription(
        user_id,
        plan=status_to_plan(status, price_id),
        status=status,
        start_date=_from_unix(subscription.get("start_date")),
        end_date=_from_unix(subscription.get("current_period_end") or subscription.get("ended_at")),
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        privileged=True,
    )


def cancel_subscription_locally(user_id: str) -> dict:
    sub = db.get_subscription(user_id) or {}
    return db.upsert_subscription(
        user_id,
        plan="free",
        status="canceled",
        stripe_customer_id=sub.get("stripe_customer_id"),
        stripe_subscription_id=sub.get("stripe_subscription_id"),
    )


def mark_paid_for_dev(user_id: str, plan: str = "premium") -> dict:
    return db.upsert_subscription(user_id, plan="premium", status="active")
