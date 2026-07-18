"""
Comprehensive Security Module
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import re
from datetime import timedelta
from functools import wraps
from typing import Any

import flask
import markupsafe
from flask import abort, request, session

from codes.core.config import is_production
from codes.services.audit_journal import audit_journal

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

SECURITY_LOGGER = logging.getLogger("graham.security")
SECURITY_LOG_LEVEL = os.environ.get("SECURITY_LOG_LEVEL", "INFO").upper()
SECURITY_LOGGER.setLevel(getattr(logging, SECURITY_LOG_LEVEL, logging.INFO))

IS_PRODUCTION = is_production()


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

_TICKER_RE = re.compile(r"^(?=.*[A-Z])[A-Z][A-Z0-9.-]{0,9}$", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_INLINE_SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)


def validate_ticker(value: Any) -> bool:
    """Validate a ticker-like symbol before it reaches downstream data APIs."""
    if not isinstance(value, str):
        return False
    ticker = value.strip()
    if not ticker or ticker.isdigit():
        return False
    return bool(_TICKER_RE.fullmatch(ticker))


def validate_email(value: Any) -> bool:
    """Validate email shape for account/billing forms without doing DNS checks."""
    if not isinstance(value, str):
        return False
    email = value.strip()
    if len(email) > 254:
        return False
    return bool(_EMAIL_RE.fullmatch(email))


def validate_numeric(
    value: Any,
    min_val: float | None = None,
    max_val: float | None = None,
) -> tuple[bool, float | None]:
    """Parse and optionally range-check a finite numeric value."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False, None

    if not parsed == parsed or parsed in (float("inf"), float("-inf")):
        return False, None
    if min_val is not None and parsed < min_val:
        return False, None
    if max_val is not None and parsed > max_val:
        return False, None
    return True, parsed


def validate_json_payload(payload: Any, max_size: int = 1_000_000) -> bool:
    """Ensure a payload is JSON-serializable and below the configured byte cap."""
    if not isinstance(payload, (dict, list)):
        return False
    try:
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        return False
    return len(encoded) <= max_size


def _mask_sensitive_details(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(re.search(pattern, key_text) for pattern in SENSITIVE_PATTERNS):
                masked[key] = "[REDACTED]"
            else:
                masked[key] = _mask_sensitive_details(item)
        return masked
    if isinstance(value, list):
        return [_mask_sensitive_details(item) for item in value]
    return value


def log_security_event(event_type: str, details: dict[str, Any] | None = None) -> None:
    """Log a security-relevant event while masking common secret-bearing fields."""
    masked = _mask_sensitive_details(details or {})
    SECURITY_LOGGER.info("SECURITY_EVENT type=%s details=%s", event_type, masked)
    audit_journal.record(
        "security",
        action=event_type,
        component="security",
        severity="WARNING",
        details=masked,
    )


class SensitiveDataEncryptor:
    """Small Fernet wrapper for encrypting sensitive local cache payloads."""

    def __init__(self):
        self.cipher = None
        if not HAS_CRYPTO:
            SECURITY_LOGGER.warning("Encryption unavailable: cryptography is not installed")
            return

        key = os.environ.get("ENCRYPTION_KEY")
        if not key:
            if is_production():
                SECURITY_LOGGER.error("ENCRYPTION_KEY is required in production")
                return
            key = Fernet.generate_key().decode("ascii")
            SECURITY_LOGGER.warning("Using ephemeral encryption key for this session")

        try:
            self.cipher = Fernet(key.encode("ascii") if isinstance(key, str) else key)
        except Exception as exc:
            SECURITY_LOGGER.error("Invalid ENCRYPTION_KEY: %s", exc)
            self.cipher = None

    def encrypt(self, plaintext: str) -> str | None:
        if self.cipher is None:
            return None
        try:
            return self.cipher.encrypt(plaintext.encode("utf-8")).decode("ascii")
        except Exception as exc:
            SECURITY_LOGGER.error("Sensitive data encryption failed: %s", exc)
            return None

    def decrypt(self, ciphertext: str) -> str | None:
        if self.cipher is None:
            return None
        try:
            return self.cipher.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except Exception as exc:
            SECURITY_LOGGER.error("Sensitive data decryption failed: %s", exc)
            return None


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
    app.config["SESSION_COOKIE_SECURE"] = is_production()
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

        if not is_production() and os.environ.get("DISABLE_CSRF_DEV") == "1":
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


def verify_csrf_token(token: str | None = None) -> bool:
    """Verify CSRF token from request."""
    if not is_production():
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
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        script_hashes = ""
        if response.mimetype == "text/html":
            hashes = {
                base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
                for script in _INLINE_SCRIPT_RE.findall(response.get_data(as_text=True))
                if script.strip()
            }
            script_hashes = " " + " ".join(f"'sha256-{value}'" for value in sorted(hashes)) if hashes else ""
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' https://browser.sentry-cdn.com https://www.clarity.ms"
            f"{script_hashes}; style-src 'self' https://fonts.googleapis.com; style-src-attr 'unsafe-inline'; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://img.logo.dev; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
        )
        if is_production():
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
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
    audit_journal.record(
        "access",
        action=action,
        actor_id=user_id,
        user_id=user_id,
        component="security",
        outcome="success" if success else "failure",
        details={"resource": resource},
    )
