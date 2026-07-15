import importlib.util
from pathlib import Path

from flask import Flask, session


spec = importlib.util.spec_from_file_location(
    "sec_008_auth_module",
    Path(__file__).resolve().parents[1] / "codes" / "auth.py",
)
auth = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(auth)


def _app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"

    @app.get("/authenticate")
    def authenticate():
        return auth.get_authenticated_user_id() or "unauthenticated"

    @app.post("/logout")
    def logout():
        auth.clear_authenticated_user()
        return "cleared"

    return app


def test_bearer_authentication_does_not_copy_token_into_session(monkeypatch):
    app = _app()
    client = app.test_client()
    monkeypatch.setattr(auth, "verify_token", lambda token: "user-123")

    response = client.get("/authenticate", headers={"Authorization": "Bearer provider-secret"})

    assert response.get_data(as_text=True) == "user-123"
    assert "provider-secret" not in response.headers.get("Set-Cookie", "")
    with client.session_transaction() as client_session:
        assert client_session["_authenticated_user_id"] == "user-123"
        assert "_auth_token" not in client_session


def test_logout_removes_legacy_client_token():
    app = _app()
    client = app.test_client()
    with client.session_transaction() as client_session:
        client_session["_authenticated_user_id"] = "user-123"
        client_session["_auth_token"] = "legacy-secret"

    client.post("/logout")

    with client.session_transaction() as client_session:
        assert "_authenticated_user_id" not in client_session
        assert "_auth_token" not in client_session
