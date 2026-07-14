import importlib.util
import sys
from pathlib import Path

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = ROOT / "codes" / "auth.py"
spec = importlib.util.spec_from_file_location("issue_013_auth", AUTH_PATH)
auth = importlib.util.module_from_spec(spec)
sys.modules["issue_013_auth"] = auth
spec.loader.exec_module(auth)



def _auth0_app(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_PROVIDER", "auth0")
    monkeypatch.setattr(auth, "AUTH0_DOMAIN", "example.auth0.com")
    monkeypatch.setattr(auth, "AUTH0_CLIENT_ID", "client-id")
    monkeypatch.setattr(auth, "AUTH0_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(auth, "CALLBACK_URL", "http://localhost/callback")

    app = Flask(__name__)
    app.secret_key = "test-secret"
    auth.setup_auth0_routes(app)
    return app


def test_callback_provider_error_does_not_reflect_raw_error(monkeypatch):
    app = _auth0_app(monkeypatch)

    response = app.test_client().get("/callback?error=<script>alert(1)</script>")

    body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert body == auth.GENERIC_AUTH_ERROR
    assert "<script>alert(1)</script>" not in body


def test_callback_token_exchange_failure_does_not_expose_response_body(monkeypatch):
    app = _auth0_app(monkeypatch)

    class FailedTokenResponse:
        status_code = 400
        text = "token exchange secret details"

    def fake_post(*args, **kwargs):
        return FailedTokenResponse()

    monkeypatch.setattr(auth.requests, "post", fake_post)

    response = app.test_client().get("/callback?code=bad-code")

    body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert body == auth.GENERIC_AUTH_ERROR
    assert "token exchange secret details" not in body
