"""
Comprehensive Security Module
"""

import os
import hashlib
import hmac
import logging
import json
import re
import time
from typing import Optional, Any, Dict, List, Tuple
from functools import wraps
from datetime import datetime, timedelta
from urllib.parse import quote, unquote
import threading
import markupsafe
import flask
from flask import request, session, abort, jsonify, has_request_context, request

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

SECURITY_LOGGER = logging.getLogger("graham.security")
SECURITY_LOG_LEVEL = os.environ.get("SECURITY_LOG_LEVEL", "INFO").upper()
SECURITY_LOGGER.setLevel(getattr(logging, SECURITY_LOG_LEVEL, logging.INFO))

IS_PRODUCTION = os.environ.get("FLASK_ENV", "").lower() == "production"

SENSITIVE_PATTERNS = [
    r"password",
    r"token",
    r"secret",
    r"api[_-]?key",
    r"credential",
    r"auth",
]

# Dash's internal callback-dispatch endpoint. All state-changing user
# actions (button clicks, form submits, portfolio edits, etc.) funnel
# through this single POST endpoint, so this is the one place a
# same-origin / CSRF check actually needs to be enforced for a Dash app.
_DASH_CALLBACK_PATH = "/_dash-update-component"
_STRIPE_WEBHOOK_PATH = "/billing/webhook"


def _generate_csrf_token() -> str:
    import secrets
    return secrets.token_urlsafe(32)

def sanitize_string(value: str, max_length: int = 500) -> str:
    """Escape HTML entities; hard length cap. Dash already auto-escapes text
    children, so this is defense-in-depth for anything passed to `title=`,
    `dangerously_allow_html`, or logged/exported raw."""
    if not value:
        return ""
    return str(markupsafe.escape(value))[:max_length]

def _same_origin(origin_or_referer: str, host: str) -> bool:
    """Compare the scheme+host of an Origin/Referer header against the request Host."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(origin_or_referer)
        req_host = urlparse(f"//{host}").netloc or host
        return parsed.netloc == req_host
    except Exception:
        return False


def init_csrf_protection(app: flask.Flask) -> None:
    """Initialize CSRF protection for the Flask app."""
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)

    @app.before_request
    def _before_request():
        """Generate CSRF token for each session."""
        if "_csrf_token" not in session:
            session["_csrf_token"] = _generate_csrf_token()
        session.modified = True

    @app.before_request
    def _enforce_same_origin_on_state_changing_requests():
        """
        Blanket CSRF defense (previously `require_csrf` was defined but never
        applied to any route/callback — this closes that gap).

        Dash routes every mutating user action (portfolio edits, add/remove
        holdings, create/delete portfolio, etc.) through a single internal
        POST endpoint, so per-callback decoration isn't possible the way it
        is for plain Flask routes. Instead, enforce a same-origin check on
        every state-changing request here — this needs no client-side
        changes (Origin/Referer are sent automatically by browsers) and
        blocks the classic CSRF attack (a foreign page submitting a request
        that rides the victim's session cookie).

        Explicit token validation (verify_csrf_token / require_csrf) remains
        available and should still be applied to any new plain Flask route.
        """
        if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
            return None

        if request.path == _STRIPE_WEBHOOK_PATH:
            return None

        if not IS_PRODUCTION and os.environ.get("DISABLE_CSRF_DEV") == "1":
            return None

        origin = request.headers.get("Origin") or request.headers.get("Referer")
        # Browsers always send Origin (or at least Referer) on cross-site
        # POSTs; a same-origin XHR/fetch from the app's own page will too.
        # Missing entirely is unusual enough to block rather than trust.
        if not origin or not request.host or not _same_origin(origin, request.host):
            SECURITY_LOGGER.warning(
                f"CSRF: rejected {request.method} {request.path} "
                f"(origin={origin!r}, host={request.host!r})"
            )
            abort(403)
        return None


def get_csrf_token() -> str:
    """Get current CSRF token from session."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = _generate_csrf_token()
    return session.get("_csrf_token", "")


def verify_csrf_token(token: Optional[str] = None) -> bool:
    """Verify CSRF token from request."""
    if not IS_PRODUCTION:
        if os.environ.get("DISABLE_CSRF_DEV") == "1":
            return True

    if not token:
        token = request.form.get("_csrf_token")

    if not token:
        token = request.headers.get("X-CSRF-Token")

    if not token and request.is_json:
        try:
            token = (request.get_json(silent=True) or {}).get("_csrf_token")
        except Exception:
            token = None

    session_token = session.get("_csrf_token", "")
    if not session_token or not token:
        return False

    return hmac.compare_digest(token, session_token)

def init_security(app: flask.Flask) -> None:
    """
    Single entrypoint called from app.py at startup.
    Wires up CSRF protection and baseline security headers.
    """
    init_csrf_protection(app)

    @app.after_request
    def _set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        if IS_PRODUCTION:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    @app.after_request
    def _cors_headers(response):
        # No cross-origin API surface today (Dash serves its own frontend).
        # Deny by default; add allow-list here if a JS client on another
        # origin needs to call this API later.
        response.headers.setdefault("Access-Control-Allow-Origin", "none")
        return response
    
    SECURITY_LOGGER.info("Security module initialized (CSRF + headers)")

def require_csrf(f):
    """Decorator to enforce CSRF protection on routes.

    Kept for explicit per-route use (e.g. Flask routes outside the Dash
    callback path, such as billing/auth POST endpoints). The blanket
    before_request hook above now covers Dash's own callback endpoint,
    so this decorator no longer needs to be applied everywhere to be
    effective — but should still be added to any new Flask POST route.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            if not verify_csrf_token():
                SECURITY_LOGGER.warning(f"CSRF token validation failed for {request.endpoint}")
                abort(403)
        return f(*args, **kwargs)
    return decorated_function

def audit_log_access(action: str, resource: str, user_id: str, success: bool = True) -> None:
    """Minimal audit trail: who did what, to which resource, outcome."""
    SECURITY_LOGGER.info(
        f"AUDIT action={action} resource={resource} user={user_id} success={success}"
    )
