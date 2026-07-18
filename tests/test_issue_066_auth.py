"""Acceptance tests for the unified ISSUE_066 authentication interface."""

from datetime import datetime, timedelta, timezone

import jwt
from flask import Flask

from codes.api.auth import TokenError, TokenService


def test_access_token_is_short_lived_and_validates_identity() -> None:
    service = TokenService("test-secret" * 8)
    pair = service.issue("user-1")
    identity = service.authenticate(pair.access_token)

    assert identity.user_id == "user-1"
    assert identity.expires_at - datetime.now(timezone.utc) <= timedelta(minutes=15)


def test_refresh_rotation_rejects_replay_and_revokes_family() -> None:
    service = TokenService("test-secret" * 8)
    pair = service.issue("user-1")
    rotated = service.rotate(pair.refresh_token)

    try:
        service.rotate(pair.refresh_token)
    except TokenError:
        pass
    else:
        raise AssertionError("refresh token replay must fail")

    try:
        service.authenticate(rotated.access_token)
    except TokenError:
        pass
    else:
        raise AssertionError("refresh replay must revoke the session family")


def test_logout_revokes_access_token_family() -> None:
    service = TokenService("test-secret" * 8)
    pair = service.issue("user-1")
    claims = jwt.decode(pair.access_token, "test-secret" * 8, algorithms=["HS256"], issuer="factorresearch")
    service.revoke_session(str(claims["sid"]))

    try:
        service.authenticate(pair.access_token)
    except TokenError:
        pass
    else:
        raise AssertionError("logout must revoke access")


def test_auth_endpoints_use_bearer_identity_and_do_not_trust_cookie(monkeypatch) -> None:
    from codes.api import auth as api_auth

    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(api_auth.auth_api)
    monkeypatch.setattr(api_auth, "token_service", TokenService("test-secret" * 8))

    with app.test_request_context():
        assert api_auth.request_identity() is None

    client = app.test_client()
    with client.session_transaction() as session:
        session["_authenticated_user_id"] = "cookie-user"
    response = client.post("/api/auth/logout")
    assert response.status_code == 401
