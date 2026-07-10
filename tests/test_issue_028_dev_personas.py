import os
import sys
from unittest.mock import Mock

import flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes import auth
from codes.services import permissions


def _app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    auth.init_auth(app)
    return app


def test_dev_impersonate_route_sets_and_clears_persona(monkeypatch):
    app = _app(monkeypatch)
    client = app.test_client()

    response = client.get("/dev/impersonate?persona=pro")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["persona"]["key"] == "pro"
    assert payload["persona"]["plan"] == "professional"

    with client.session_transaction() as session:
        assert session[auth.DEV_PERSONA_SESSION_KEY] == "pro"

    response = client.get("/dev/impersonate?persona=clear")
    assert response.status_code == 200
    assert response.get_json()["persona"] is None

    with client.session_transaction() as session:
        assert auth.DEV_PERSONA_SESSION_KEY not in session


def test_dev_impersonate_route_rejects_unknown_persona(monkeypatch):
    app = _app(monkeypatch)
    client = app.test_client()

    response = client.get("/dev/impersonate?persona=enterprise")

    assert response.status_code == 400
    assert "available" in response.get_json()


def test_paid_persona_bypasses_subscription_db(monkeypatch):
    app = _app(monkeypatch)
    db_lookup = Mock(side_effect=AssertionError("DB subscription lookup should not run"))
    monkeypatch.setattr(permissions.db, "get_subscription", db_lookup)

    with app.test_request_context("/"):
        flask.session[auth.DEV_PERSONA_SESSION_KEY] = "paid"
        user_id = auth.get_authenticated_user_id()
        result = permissions.can_access_feature(user_id, permissions.Feature.BACKTEST)

    assert user_id == "dev-paid-user"
    assert result.allowed is True
    assert result.plan == "premium"


def test_free_persona_behaves_like_trial_user(monkeypatch):
    app = _app(monkeypatch)
    monkeypatch.setattr(permissions.db, "get_total_usage", lambda *_: 0)

    with app.test_request_context("/"):
        flask.session[auth.DEV_PERSONA_SESSION_KEY] = "free"
        user_id = auth.get_authenticated_user_id()
        analysis = permissions.can_access_feature(user_id, permissions.Feature.ANALYSIS)
        backtest = permissions.can_access_feature(user_id, permissions.Feature.BACKTEST)

    assert user_id == "dev-free-user"
    assert analysis.allowed is True
    assert analysis.remaining == 3
    assert backtest.allowed is False
    assert backtest.plan == "trial"
