import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask

spec = importlib.util.spec_from_file_location(
    "issue_018_auth_module",
    Path(__file__).resolve().parents[1] / "codes" / "auth.py",
)
auth = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(auth)


@pytest.fixture
def app(monkeypatch):
    flask_app = Flask(__name__)
    flask_app.secret_key = "test-secret"

    monkeypatch.setattr(auth, "AUTH_PROVIDER", "auth0")
    monkeypatch.setattr(auth, "AUTH0_DOMAIN", "example.auth0.com")
    monkeypatch.setattr(auth, "AUTH0_CLIENT_ID", "client-id")
    monkeypatch.setattr(auth, "AUTH0_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(auth, "CALLBACK_URL", "http://localhost/callback")

    auth.setup_auth0_routes(flask_app)
    return flask_app


def test_login_includes_state_parameter(app):
    client = app.test_client()

    response = client.get("/login")

    assert response.status_code == 302
    parsed = urlparse(response.headers["Location"])
    query = parse_qs(parsed.query)
    assert query["state"][0]
    with client.session_transaction() as session:
        assert session[auth.AUTH0_OAUTH_STATE_KEY] == query["state"][0]


def test_callback_rejects_missing_state_before_token_exchange(app, monkeypatch):
    client = app.test_client()
    token_called = False

    def fake_post(*args, **kwargs):
        nonlocal token_called
        token_called = True
        raise AssertionError("token exchange should not run")

    monkeypatch.setattr(auth.requests, "post", fake_post)

    client.get("/login")

    response = client.get("/callback", query_string={"code": "auth-code"})

    assert response.status_code == 400
    assert not token_called
    with client.session_transaction() as session:
        assert auth.AUTH0_OAUTH_STATE_KEY not in session


def test_callback_rejects_mismatched_state_before_token_exchange(app, monkeypatch):
    client = app.test_client()
    token_called = False

    def fake_post(*args, **kwargs):
        nonlocal token_called
        token_called = True
        raise AssertionError("token exchange should not run")

    monkeypatch.setattr(auth.requests, "post", fake_post)

    client.get("/login")

    response = client.get("/callback", query_string={"code": "auth-code", "state": "wrong-state"})

    assert response.status_code == 400
    assert not token_called
    with client.session_transaction() as session:
        assert auth.AUTH0_OAUTH_STATE_KEY not in session


def test_callback_accepts_matching_state_and_exchanges_token(app, monkeypatch):
    client = app.test_client()
    token_called = False

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"access_token": "access-token"}

    def fake_post(*args, **kwargs):
        nonlocal token_called
        token_called = True
        return FakeResponse()

    monkeypatch.setattr(auth.requests, "post", fake_post)
    monkeypatch.setattr(auth, "verify_token", lambda token: "user-123")

    response = client.get("/login")
    state = parse_qs(urlparse(response.headers["Location"]).query)["state"][0]

    response = client.get("/callback", query_string={"code": "auth-code", "state": state})

    assert response.status_code == 302
    assert token_called
    with client.session_transaction() as session:
        assert session["_authenticated_user_id"] == "user-123"
        assert auth.AUTH0_OAUTH_STATE_KEY not in session
