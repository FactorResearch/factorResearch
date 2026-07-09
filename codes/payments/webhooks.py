"""Stripe webhook event handling."""

from __future__ import annotations

from codes.payments import subscriptions


HANDLED_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
}


def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict_recursive"):
        return value.to_dict_recursive()
    try:
        return dict(value)
    except Exception:
        return {}


def handle_event(event) -> bool:
    event_type = event.get("type") if isinstance(event, dict) else getattr(event, "type", "")
    data = event.get("data", {}) if isinstance(event, dict) else getattr(event, "data", {})
    obj = data.get("object") if isinstance(data, dict) else getattr(data, "object", None)
    if obj is None:
        return False

    if event_type == "checkout.session.completed":
        subscriptions.sync_checkout_completed(_as_dict(obj))
        return True

    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        subscriptions.sync_subscription(_as_dict(obj))
        return True

    if event_type == "invoice.payment_failed":
        invoice = _as_dict(obj)
        subscription_id = invoice.get("subscription")
        customer_id = invoice.get("customer")
        if subscription_id or customer_id:
            pseudo_subscription = {
                "id": subscription_id,
                "customer": customer_id,
                "status": "past_due",
                "metadata": {},
            }
            subscriptions.sync_subscription(pseudo_subscription)
        return True

    return False
