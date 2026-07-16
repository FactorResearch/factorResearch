"""Billing routes and compatibility helpers."""

from __future__ import annotations

from urllib.parse import urlencode

import flask
from codes.core import app_flags
from codes.core.config import is_production
from codes.app_modules.session import get_user_id
from codes.payments import stripe_client, subscriptions, webhooks
from codes.services import permissions
from codes.services import product_analytics


def init_billing(server: flask.Flask | None = None):
    if server is None:
        return

    @server.route("/billing/checkout", methods=["GET"])
    def _checkout():
        plan = flask.request.args.get("plan", "premium").lower()
        source = flask.request.args.get("source", "direct")
        feature = flask.request.args.get("feature", "")
        if plan != "premium":
            return "Only the Premium plan is available.", 400
        try:
            user_id = get_user_id()
        except RuntimeError:
            return "missing user_id", 400
        try:
            product_analytics.track_event(
                user_id,
                "upgrade_clicked",
                {"plan": plan, "source": source, "feature": feature},
            )
            product_analytics.track_event(
                user_id,
                "subscription_started",
                {"plan": plan, "source": source, "feature": feature},
            )
            return flask.redirect(get_checkout_url(user_id, plan=plan))
        except Exception as exc:
            if is_production():
                return "Billing is unavailable. Please try again later.", 503
            return f"Billing unavailable: {type(exc).__name__}: {exc}", 503

    @server.route("/billing/portal", methods=["GET"])
    def _portal():
        try:
            user_id = get_user_id()
        except RuntimeError:
            return "missing user_id", 400
        try:
            return flask.redirect(get_portal_url(user_id))
        except Exception as exc:
            if is_production():
                return "Billing portal is unavailable. Please try again later.", 503
            return f"Billing portal unavailable: {type(exc).__name__}: {exc}", 503

    @server.route("/billing/success", methods=["GET"])
    def _success():
        return flask.redirect("/")

    @server.route("/billing/webhook", methods=["POST"])
    def _stripe_webhook():
        payload = flask.request.get_data()
        signature = flask.request.headers.get("Stripe-Signature")
        try:
            event = stripe_client.construct_webhook_event(payload, signature)
        except Exception:
            return flask.jsonify({"error": "invalid webhook"}), 400
        handled = webhooks.handle_event(event)
        return flask.jsonify({"received": True, "handled": handled})

    if not is_production():
        @server.route("/billing/mark_paid", methods=["GET"])
        def _mark_paid():
            try:
                uid = get_user_id()
            except RuntimeError:
                return "missing user_id", 400
            subscriptions.mark_paid_for_dev(uid)
            flask.session["is_paid"] = True
            return flask.redirect(flask.request.referrer or "/")


def user_has_paid(user_id: str) -> bool:
    if app_flags.billing_checks_disabled():
        return True
    if not user_id:
        return False
    try:
        if flask.session.get("is_paid") and not is_production():
            return True
    except Exception:
        pass
    return permissions.is_paid_subscription(permissions.get_or_create_subscription(user_id))


def get_checkout_url(user_id: str, plan: str = "premium") -> str:
    if plan.lower() != "premium":
        raise ValueError("Only the Premium plan is available.")
    if stripe_client.is_configured():
        return stripe_client.create_checkout_session(user_id, plan=plan)
    if is_production():
        raise RuntimeError("Stripe checkout is not configured in production.")
    return "/billing/mark_paid"


def get_billing_entry_url(plan: str = "premium", **context: str | None) -> str:
    if plan.lower() != "premium":
        raise ValueError("Only the Premium plan is available.")
    params = {"plan": plan}
    for key, value in context.items():
        if value:
            params[key] = value
    return f"/billing/checkout?{urlencode(params)}"


def get_portal_url(user_id: str) -> str:
    if stripe_client.is_configured():
        return stripe_client.create_billing_portal_session(user_id)
    if is_production():
        raise RuntimeError("Stripe portal is not configured in production.")
    return "/billing/mark_paid"
