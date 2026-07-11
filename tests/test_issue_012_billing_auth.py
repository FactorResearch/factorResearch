import sys
import types
import importlib.util
from pathlib import Path

import flask


ROOT = Path(__file__).resolve().parents[1]


def _billing_module(monkeypatch):
    def get_user_id():
        uid = flask.session.get("_uid")
        if not uid:
            raise RuntimeError("missing user")
        return uid

    codes = types.ModuleType("codes")
    app_modules = types.ModuleType("codes.app_modules")
    session = types.ModuleType("codes.app_modules.session")
    session.get_user_id = get_user_id

    payments = types.ModuleType("codes.payments")
    payments.stripe_client = types.SimpleNamespace(
        is_configured=lambda: False,
        create_checkout_session=lambda *args, **kwargs: None,
        create_billing_portal_session=lambda *args, **kwargs: None,
        construct_webhook_event=lambda *args, **kwargs: None,
    )
    payments.subscriptions = types.SimpleNamespace(mark_paid_for_dev=lambda user_id: None)
    payments.webhooks = types.SimpleNamespace(handle_event=lambda event: True)

    services = types.ModuleType("codes.services")
    services.permissions = types.SimpleNamespace(
        is_paid_subscription=lambda subscription: False,
        get_or_create_subscription=lambda user_id: {},
    )
    services.product_analytics = types.SimpleNamespace(track_event=lambda *args, **kwargs: None)

    monkeypatch.setitem(sys.modules, "codes", codes)
    monkeypatch.setitem(sys.modules, "codes.app_modules", app_modules)
    monkeypatch.setitem(sys.modules, "codes.app_modules.session", session)
    monkeypatch.setitem(sys.modules, "codes.payments", payments)
    monkeypatch.setitem(sys.modules, "codes.services", services)
    monkeypatch.setitem(sys.modules, "codes.services.product_analytics", services.product_analytics)

    spec = importlib.util.spec_from_file_location("issue012_billing", ROOT / "codes" / "billing.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _client(monkeypatch, billing):
    monkeypatch.setenv("FLASK_ENV", "development")
    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    billing.init_billing(app)
    return app.test_client()


def test_checkout_ignores_user_id_query(monkeypatch):
    billing = _billing_module(monkeypatch)
    client = _client(monkeypatch, billing)
    seen = {}

    def fake_checkout(user_id, plan="premium"):
        seen["user_id"] = user_id
        seen["plan"] = plan
        return f"/checkout/{user_id}/{plan}"

    monkeypatch.setattr(billing, "get_checkout_url", fake_checkout)
    with client.session_transaction() as session:
        session["_uid"] = "current_user"

    response = client.get("/billing/checkout?user_id=other_user&plan=premium")

    assert response.status_code == 302
    assert response.headers["Location"] == "/checkout/current_user/premium"
    assert seen == {"user_id": "current_user", "plan": "premium"}


def test_checkout_rejects_retired_plan(monkeypatch):
    billing = _billing_module(monkeypatch)
    client = _client(monkeypatch, billing)
    with client.session_transaction() as session:
        session["_uid"] = "current_user"

    response = client.get("/billing/checkout?plan=professional")

    assert response.status_code == 400
    assert b"Only the Premium plan" in response.data


def test_portal_ignores_user_id_query(monkeypatch):
    billing = _billing_module(monkeypatch)
    client = _client(monkeypatch, billing)
    seen = {}

    def fake_portal(user_id):
        seen["user_id"] = user_id
        return f"/portal/{user_id}"

    monkeypatch.setattr(billing, "get_portal_url", fake_portal)
    with client.session_transaction() as session:
        session["_uid"] = "current_user"

    response = client.get("/billing/portal?user_id=other_user")

    assert response.status_code == 302
    assert response.headers["Location"] == "/portal/current_user"
    assert seen == {"user_id": "current_user"}
