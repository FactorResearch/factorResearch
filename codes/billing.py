"""Billing integration (Stripe + dev fallback).

Provides a minimal interface for checkout/portal URL generation and
simple per-user tier checks. In production set `STRIPE_SECRET_KEY` and
`STRIPE_PRICE_ID` env vars to enable real Stripe flows. For local
development the module exposes a small demo route to mark the current
session as paid.
"""
from typing import Optional
import os
import flask

STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")

_paid_users: dict[str, bool] = {}


def init_billing(server: Optional[flask.Flask] = None):
    """Initialize billing endpoints on the Flask `server` when available.

    Adds a lightweight dev helper at `/billing/mark_paid` to mark the
    current session as paid for local testing. In production you should
    create real Checkout/Portal sessions using Stripe's SDK.
    """
    if server is None:
        return

    @server.route("/billing/mark_paid", methods=["GET"])
    def _mark_paid():
        # For local/dev testing only: marks the session as paid and redirects back.
        uid = flask.request.args.get("user_id") or flask.session.get("_uid")
        if not uid:
            return "missing user_id", 400
        _paid_users[uid] = True
        # Also set session flag for immediate effect in local dev.
        flask.session["is_paid"] = True
        return flask.redirect(flask.request.referrer or "/")


def user_has_paid(user_id: str) -> bool:
    """Return True if `user_id` is in the paid set or session indicates paid.

    This function intentionally keeps logic simple: in production you
    should map application user IDs to Stripe Customer + Subscription
    records and check subscription status server-side.
    """
    try:
        if not user_id:
            return False
        # Check explicit in-memory mapping first
        if _paid_users.get(user_id):
            return True
        # Check Flask session (useful for local dev flow)
        if flask.session.get("is_paid"):
            return True
    except Exception:
        pass
    return False


def get_checkout_url(user_id: str) -> str:
    """Return a checkout/upgrade URL for the user.

    If Stripe isn't configured, return a lightweight dev URL that marks
    the session as paid when visited (`/billing/mark_paid`).
    """
    if STRIPE_KEY and STRIPE_PRICE_ID:
        # Production: you'd create a Stripe Checkout Session here and return its URL.
        # Keep this non-failing if stripe isn't installed; leave the implementation
        # to the deployer.
        try:
            import stripe
            stripe.api_key = STRIPE_KEY
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
                mode="subscription",
                success_url="/billing/upgrade_success",
                cancel_url="/",
            )
            return session.url
        except Exception:
            # Fall through to dev URL on any failure
            pass
    # Dev fallback: provide a URL that will mark the session paid
    return f"/billing/mark_paid?user_id={user_id}"


def get_portal_url(user_id: str) -> str:
    """Return a customer portal URL (or dev fallback).

    Production should call Stripe's billing portal API. Here we return
    a simple link for local testing.
    """
    if STRIPE_KEY:
        try:
            import stripe
            stripe.api_key = STRIPE_KEY
            # Real portal creation omitted for brevity.
        except Exception:
            pass
    return f"/billing/mark_paid?user_id={user_id}"
