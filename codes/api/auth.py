"""Provider-neutral first-party token lifecycle for API clients.

The adapter exchanges a provider-validated identity for short-lived access and
rotating refresh tokens. Raw tokens are never retained after issuance;
revocation state is keyed by a SHA-256 digest and refresh-token reuse revokes
the complete session family. This module is deliberately independent of Flask
session state so browser, mobile, and service clients receive the same identity
boundary.

The current store is process-local because the repository's optional database
is not guaranteed at application startup. Production deployments must use one
shared store (or a single-process deployment) before relying on revocation
across workers; the API exposes no refresh token persistence contract yet.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

import flask
import jwt

from codes.core.config import get_config, is_production

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)
_ISSUER = "factorresearch"


class TokenError(ValueError):
    """Raised when a token is malformed, expired, revoked, or misused."""


@dataclass(frozen=True)
class TokenIdentity:
    """Validated request identity and lifecycle metadata, without secrets."""

    user_id: str
    token_id: str
    session_id: str
    expires_at: datetime


@dataclass(frozen=True)
class TokenPair:
    """Access and refresh credentials returned only at issuance/rotation."""

    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


@dataclass
class _Session:
    user_id: str
    expires_at: datetime
    revoked: bool = False


class TokenService:
    """Issue, validate, rotate, and revoke signed first-party credentials."""

    def __init__(self, secret: str | None = None) -> None:
        configured = secret or str(get_config("AUTH_TOKEN_SECRET") or "")
        fallback = str(get_config("FLASK_SECRET_KEY") or "")
        if not configured and not is_production():
            configured = fallback
        if is_production() and len(configured) < 32:
            raise RuntimeError("AUTH_TOKEN_SECRET must be at least 32 characters in production.")
        self._secret = configured or secrets.token_urlsafe(32)
        self._sessions: dict[str, _Session] = {}
        self._revoked_tokens: dict[str, datetime] = {}
        self._lock = RLock()

    def issue(self, user_id: str, *, now: datetime | None = None) -> TokenPair:
        """Create a new independent session for a validated user identity."""
        subject = str(user_id or "").strip()
        if not subject:
            raise TokenError("user identity is required")
        current = _utc(now)
        session_id = secrets.token_urlsafe(18)
        with self._lock:
            self._sessions[session_id] = _Session(subject, current + REFRESH_TOKEN_TTL)
            return self._pair(subject, session_id, current)

    def authenticate(self, token: str, *, now: datetime | None = None) -> TokenIdentity:
        """Validate an access token and enforce expiry and revocation state."""
        claims = self._decode(token, expected_type="access", now=now)
        identity = self._identity(claims)
        with self._lock:
            session = self._sessions.get(identity.session_id)
            if not session or session.revoked or session.user_id != identity.user_id:
                raise TokenError("session is revoked or unavailable")
        return identity

    def rotate(self, refresh_token: str, *, now: datetime | None = None) -> TokenPair:
        """Rotate a refresh token; reuse revokes the entire session family."""
        # Decode once without the revocation check so a replay can identify and
        # revoke its session family rather than merely returning 401.
        claims = self._decode(refresh_token, expected_type="refresh", now=now, check_revocation=False)
        current = _utc(now)
        token_digest = _digest(refresh_token)
        session_id = str(claims.get("sid") or "")
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or session.revoked or session.expires_at <= current:
                if session:
                    session.revoked = True
                raise TokenError("refresh session is revoked or unavailable")
            if token_digest in self._revoked_tokens:
                session.revoked = True
                raise TokenError("refresh token reuse detected")
            self._revoked_tokens[token_digest] = datetime.fromtimestamp(
                float(claims["exp"]), tz=timezone.utc
            )
            return self._pair(session.user_id, session_id, current)

    def revoke_token(self, token: str) -> None:
        """Revoke one access or refresh token without logging its value."""
        try:
            claims = self._decode(token, expected_type=None)
        except TokenError:
            return
        expiry = datetime.fromtimestamp(float(claims["exp"]), tz=timezone.utc)
        with self._lock:
            self._revoked_tokens[_digest(token)] = expiry

    def revoke_session(self, session_id: str) -> None:
        """Revoke all credentials in one browser/mobile session family."""
        with self._lock:
            session = self._sessions.get(str(session_id or ""))
            if session:
                session.revoked = True

    def _pair(self, user_id: str, session_id: str, now: datetime) -> TokenPair:
        access_expiry = now + ACCESS_TOKEN_TTL
        refresh_expiry = now + REFRESH_TOKEN_TTL
        access = self._encode(user_id, session_id, "access", now, access_expiry)
        refresh = self._encode(user_id, session_id, "refresh", now, refresh_expiry)
        return TokenPair(access, refresh, access_expiry, refresh_expiry)

    def _encode(
        self, user_id: str, session_id: str, token_type: str, issued_at: datetime, expires_at: datetime
    ) -> str:
        return str(jwt.encode({
            "sub": user_id,
            "sid": session_id,
            "jti": secrets.token_urlsafe(18),
            "typ": token_type,
            "iss": _ISSUER,
            "iat": issued_at,
            "exp": expires_at,
        }, self._secret, algorithm="HS256"))

    def _decode(
        self,
        token: str,
        *,
        expected_type: str | None,
        now: datetime | None = None,
        check_revocation: bool = True,
    ) -> dict[str, Any]:
        if not token or not isinstance(token, str):
            raise TokenError("token is required")
        try:
            claims = jwt.decode(token, self._secret, algorithms=["HS256"], issuer=_ISSUER)
        except jwt.PyJWTError as exc:
            raise TokenError("token validation failed") from exc
        if expected_type and claims.get("typ") != expected_type:
            raise TokenError("wrong token type")
        if not claims.get("sub") or not claims.get("sid") or not claims.get("jti"):
            raise TokenError("token claims are incomplete")
        current = _utc(now)
        if datetime.fromtimestamp(float(claims["exp"]), tz=timezone.utc) <= current:
            raise TokenError("token expired")
        with self._lock:
            if not check_revocation:
                return claims
            digest = _digest(token)
            expiry = self._revoked_tokens.get(digest)
            if expiry and expiry > current:
                raise TokenError("token revoked")
            if expiry and expiry <= current:
                self._revoked_tokens.pop(digest, None)
        return claims

    @staticmethod
    def _identity(claims: dict[str, Any]) -> TokenIdentity:
        return TokenIdentity(
            user_id=str(claims["sub"]),
            token_id=str(claims["jti"]),
            session_id=str(claims["sid"]),
            expires_at=datetime.fromtimestamp(float(claims["exp"]), tz=timezone.utc),
        )


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current.astimezone(timezone.utc) if current.tzinfo else current.replace(tzinfo=timezone.utc)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


token_service = TokenService()
auth_api = flask.Blueprint("auth_api", __name__, url_prefix="/api/auth")


def bearer_token() -> str | None:
    """Extract exactly one Bearer credential from the current request."""
    header = flask.request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def request_identity() -> TokenIdentity | None:
    """Return the unified first-party identity for the current request."""
    token = bearer_token()
    if not token:
        return None
    try:
        return token_service.authenticate(token)
    except TokenError:
        return None


@auth_api.post("/token")
def exchange_token():
    """Exchange an already provider-validated Bearer token for first-party credentials."""
    from codes import auth as provider_auth

    provider_token = bearer_token()
    user_id = provider_auth.verify_token(provider_token or "")
    if not user_id:
        return flask.jsonify({"error": {"code": "unauthorized", "message": "Authentication is required."}}), 401
    pair = token_service.issue(user_id)
    return flask.jsonify(_pair_response(pair)), 201


@auth_api.post("/refresh")
def refresh_token():
    """Rotate a refresh token and invalidate the presented refresh credential."""
    payload = flask.request.get_json(silent=True) or {}
    try:
        pair = token_service.rotate(str(payload.get("refresh_token") or ""))
    except TokenError:
        return flask.jsonify({"error": {"code": "unauthorized", "message": "Refresh session is invalid."}}), 401
    return flask.jsonify(_pair_response(pair)), 200


@auth_api.post("/logout")
def logout():
    """Revoke the current access-token session family."""
    identity = request_identity()
    if not identity:
        return flask.jsonify({"error": {"code": "unauthorized", "message": "Authentication is required."}}), 401
    token_service.revoke_session(identity.session_id)
    return flask.jsonify({"ok": True}), 200


def _pair_response(pair: TokenPair) -> dict[str, Any]:
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()),
        "refresh_expires_in": int(REFRESH_TOKEN_TTL.total_seconds()),
    }
