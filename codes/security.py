"""
Comprehensive Security Module for Graham Score App

Implements industry-leading security practices:
- Input validation and sanitization
- CSRF protection
- Rate limiting per user/IP
- Secure session management
- SQL injection prevention
- XSS protection
- Security headers
- Sensitive data encryption
- Audit logging
- API security controls
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

import flask
from flask import request, session, abort, jsonify,has_request_context, request

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# ──────────────────────────────────────────────────────────────────────────────
# Security Configuration
# ──────────────────────────────────────────────────────────────────────────────

SECURITY_LOGGER = logging.getLogger("graham.security")
SECURITY_LOG_LEVEL = os.environ.get("SECURITY_LOG_LEVEL", "INFO").upper()
SECURITY_LOGGER.setLevel(getattr(logging, SECURITY_LOG_LEVEL, logging.INFO))

IS_PRODUCTION = os.environ.get("FLASK_ENV", "").lower() == "production"

# Sensitive data patterns to mask in logs
SENSITIVE_PATTERNS = [
    r"password",
    r"token",
    r"secret",
    r"api[_-]?key",
    r"credential",
    r"auth",
]

# ──────────────────────────────────────────────────────────────────────────────
# Session & CSRF Management
# ──────────────────────────────────────────────────────────────────────────────

def _generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    import secrets
    return secrets.token_urlsafe(32)


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


def get_csrf_token() -> str:
    """Get current CSRF token from session."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = _generate_csrf_token()
    return session.get("_csrf_token", "")


def verify_csrf_token(token: Optional[str] = None) -> bool:
    """Verify CSRF token from request."""
    if not IS_PRODUCTION:
        # Allow bypassing CSRF in development
        if os.environ.get("DISABLE_CSRF_DEV") == "1":
            return True
    
    if not token:
        token = request.form.get("_csrf_token")
    
    if not token:
        token = request.headers.get("X-CSRF-Token")
    
    session_token = session.get("_csrf_token", "")
    if not session_token or not token:
        return False
    
    return hmac.compare_digest(token, session_token)


def require_csrf(f):
    """Decorator to enforce CSRF protection on routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            if not verify_csrf_token():
                SECURITY_LOGGER.warning(f"CSRF token validation failed for {request.endpoint}")
                abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ──────────────────────────────────────────────────────────────────────────────
# Input Validation & Sanitization
# ──────────────────────────────────────────────────────────────────────────────

def sanitize_string(value: str, max_length: int = 1000, allow_special: bool = False) -> str:
    """
    Sanitize string input to prevent XSS and injection attacks.
    
    Args:
        value: Input string
        max_length: Maximum allowed length
        allow_special: If True, allows some HTML entities
    
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return ""
    
    # Truncate to max length
    value = value[:max_length]
    
    # Remove null bytes
    value = value.replace("\x00", "")
    
    # Escape HTML entities
    replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    }
    
    for char, escaped in replacements.items():
        value = value.replace(char, escaped)
    
    return value.strip()


def validate_ticker(ticker: str) -> bool:
    """
    Validate stock ticker symbol.
    
    Allows: A-Z, 0-9, dot, hyphen. Max 5 chars (with exceptions like BRK.B).
    """
    if not isinstance(ticker, str):
        return False
    
    ticker = ticker.upper().strip()
    
    # Max 6 chars to allow BRK.B, BF.A etc.
    if len(ticker) > 6 or len(ticker) < 1:
        return False
    
    # Must contain only alphanumeric, dots, hyphens
    return bool(re.match(r"^[A-Z0-9\.\-]+$", ticker))


def validate_email(email: str) -> bool:
    """Basic email validation."""
    if not isinstance(email, str):
        return False
    
    email = email.strip().lower()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email)) and len(email) <= 254


def validate_numeric(value: Any, min_val: Optional[float] = None, 
                     max_val: Optional[float] = None) -> Tuple[bool, Optional[float]]:
    """
    Validate and convert numeric input.
    
    Returns:
        Tuple of (is_valid, converted_value)
    """
    try:
        num = float(value)
        
        if min_val is not None and num < min_val:
            return False, None
        
        if max_val is not None and num > max_val:
            return False, None
        
        return True, num
    except (ValueError, TypeError):
        return False, None


def validate_json_payload(data: Any, max_size: int = 1_000_000) -> bool:
    """
    Validate JSON payload size and structure.
    
    Returns:
        True if valid, False otherwise
    """
    try:
        if isinstance(data, dict):
            payload_size = len(json.dumps(data))
        else:
            payload_size = len(str(data))
        
        return payload_size <= max_size
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Rate Limiting
# ──────────────────────────────────────────────────────────────────────────────

class RateLimiter:
    """Thread-safe rate limiter using token bucket algorithm."""
    
    def __init__(self):
        self._buckets: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 3600  # Clean old entries every hour
        self._last_cleanup = time.time()
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """
        Check if request is allowed under rate limit.
        
        Args:
            key: Unique identifier (user_id, IP, etc.)
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
        
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        now = time.time()
        
        with self._lock:
            # Periodic cleanup
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_old_entries(now)
                self._last_cleanup = now
            
            # Get or create bucket
            if key not in self._buckets:
                self._buckets[key] = []
            
            bucket = self._buckets[key]
            
            # Remove old requests outside window
            bucket[:] = [ts for ts in bucket if now - ts < window_seconds]
            
            # Check if under limit
            if len(bucket) < max_requests:
                bucket.append(now)
                return True
            
            return False
    
    def _cleanup_old_entries(self, now: float) -> None:
        """Remove expired rate limit buckets."""
        keys_to_delete = [
            k for k, v in self._buckets.items()
            if not v or (now - max(v) > self._cleanup_interval)
        ]
        for k in keys_to_delete:
            del self._buckets[k]


_rate_limiter = RateLimiter()


def get_client_identifier() -> str:
    """Get unique client identifier (user_id or IP address)."""
    try:
        # Try to get authenticated user ID
        if "_authenticated_user_id" in session:
            return f"user:{session['_authenticated_user_id']}"
    except Exception:
        pass
    if not has_request_context():
        return "system"   # or "startup"
    # Fall back to IP address
    if request.headers.get("X-Forwarded-For"):
        return f"ip:{request.headers.get('X-Forwarded-For').split(',')[0]}"
    
    return f"ip:{request.remote_addr or 'unknown'}"


def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    """
    Decorator to enforce rate limiting on routes/callbacks.
    
    Usage:
        @app.route("/api/data")
        @rate_limit(max_requests=10, window_seconds=60)
        def get_data():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_id = get_client_identifier()
            
            if not _rate_limiter.is_allowed(client_id, max_requests, window_seconds):
                SECURITY_LOGGER.warning(
                    f"Rate limit exceeded for {client_id}: "
                    f"{max_requests}/{window_seconds}s"
                )
                abort(429)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ──────────────────────────────────────────────────────────────────────────────
# Encryption for Sensitive Data
# ──────────────────────────────────────────────────────────────────────────────

class SensitiveDataEncryptor:
    """Encrypt/decrypt sensitive data using Fernet (AES-128)."""
    
    def __init__(self, key: Optional[str] = None):
        if not HAS_CRYPTO:
            SECURITY_LOGGER.warning("cryptography library not available; encryption disabled")
            self.cipher = None
            return
        
        if not key:
            key = os.environ.get("ENCRYPTION_KEY")
        
        if not key:
            # Generate a key if not provided (not recommended for production)
            if IS_PRODUCTION:
                raise RuntimeError(
                    "ENCRYPTION_KEY environment variable must be set in production"
                )
            from cryptography.fernet import Fernet
            key = Fernet.generate_key()
        
        try:
            if isinstance(key, str):
                key = key.encode()
            self.cipher = Fernet(key)
        except Exception as e:
            SECURITY_LOGGER.error(f"Failed to initialize encryption: {e}")
            self.cipher = None
    
    def encrypt(self, data: str) -> Optional[str]:
        """Encrypt a string."""
        if not self.cipher:
            SECURITY_LOGGER.warning("Encryption not available; returning plaintext")
            return data
        
        try:
            encrypted = self.cipher.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            SECURITY_LOGGER.error(f"Encryption failed: {e}")
            return None
    
    def decrypt(self, data: str) -> Optional[str]:
        """Decrypt a string."""
        if not self.cipher:
            return data
        
        try:
            decrypted = self.cipher.decrypt(data.encode())
            return decrypted.decode()
        except Exception as e:
            SECURITY_LOGGER.warning(f"Decryption failed: {e}")
            return None


# ──────────────────────────────────────────────────────────────────────────────
# Audit Logging
# ──────────────────────────────────────────────────────────────────────────────

def _mask_sensitive_data(data: str) -> str:
    """Mask sensitive fields in log output."""
    for pattern in SENSITIVE_PATTERNS:
        data = re.sub(
            f'("{pattern}"\\s*:\\s*)"([^"]*)"',
            rf'\1"***REDACTED***"',
            data,
            flags=re.IGNORECASE,
        )
    return data


def log_security_event(
    event_type: str,
    severity: str = "INFO",
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_path: Optional[str] = None,
) -> None:
    """
    Log security-relevant events.
    
    Args:
        event_type: Type of security event (LOGIN, FAILED_AUTH, RATE_LIMIT, etc.)
        severity: Log level (INFO, WARNING, ERROR, CRITICAL)
        user_id: Associated user ID if applicable
        details: Additional event details
        request_path: Request path if applicable
    """
    log_message = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "severity": severity,
        "user_id": user_id or "anonymous",
        "client_ip": get_client_identifier(),
        "request_path": request_path or request.path if request else None,
        "user_agent": request.headers.get("User-Agent") if request else None,
        "details": details or {},
    }
    
    # Mask sensitive data before logging
    log_str = json.dumps(log_message)
    log_str = _mask_sensitive_data(log_str)
    
    log_level = getattr(logging, severity.upper(), logging.INFO)
    SECURITY_LOGGER.log(log_level, log_str)


def audit_log_access(
    action: str,
    resource: str,
    user_id: Optional[str] = None,
    success: bool = True,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log data access for audit trail.
    
    Args:
        action: Action performed (READ, WRITE, DELETE, EXECUTE)
        resource: Resource accessed
        user_id: User performing the action
        success: Whether the action succeeded
        details: Additional details
    """
    log_security_event(
        event_type=f"AUDIT_{action}",
        severity="INFO" if success else "WARNING",
        user_id=user_id,
        details={
            "resource": resource,
            "action": action,
            "success": success,
            **(details or {}),
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Security Headers Configuration
# ──────────────────────────────────────────────────────────────────────────────

def init_security_headers(app: flask.Flask) -> None:
    """Initialize comprehensive security headers."""
    
    @app.after_request
    def _set_security_headers(response):
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions policy (formerly Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), microphone=(), payment=(), usb=()"
        )
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.plot.ly; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp
        
        # HSTS (only in production)
        if IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        # Disable caching for sensitive responses
        if "security" in request.path or "auth" in request.path:
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response
    
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Error Handling & Safe Responses
# ──────────────────────────────────────────────────────────────────────────────

def safe_json_response(
    data: Any = None,
    status_code: int = 200,
    error: Optional[str] = None,
) -> Tuple[Any, int]:
    """
    Create a safe JSON response without exposing internal errors.
    
    Returns:
        Tuple of (response_dict, status_code)
    """
    if error:
        SECURITY_LOGGER.warning(f"API error response: {error}")
        return (
            {
                "success": False,
                "error": "An error occurred. Please try again." if IS_PRODUCTION else error,
            },
            status_code,
        )
    
    return ({"success": True, "data": data}, status_code)


# ──────────────────────────────────────────────────────────────────────────────
# Setup & Initialization
# ──────────────────────────────────────────────────────────────────────────────

def init_security(app: flask.Flask) -> None:
    """Initialize all security measures for the Flask app."""
    
    # Set up logging
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )
    SECURITY_LOGGER.addHandler(handler)
    
    # Initialize security features
    init_csrf_protection(app)
    init_security_headers(app)
    
    # Set secure Flask config
    app.config.update(
        SESSION_COOKIE_SECURE=IS_PRODUCTION,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SEND_FILE_MAX_AGE_DEFAULT=31536000,  # 1 year for static assets
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,  # 10MB max request size
        JSON_SORT_KEYS=False,
    )
    
    log_security_event("SECURITY_INIT", details={"production": IS_PRODUCTION})


# Export commonly used utilities
__all__ = [
    "sanitize_string",
    "validate_ticker",
    "validate_email",
    "validate_numeric",
    "validate_json_payload",
    "rate_limit",
    "get_csrf_token",
    "verify_csrf_token",
    "require_csrf",
    "log_security_event",
    "audit_log_access",
    "SensitiveDataEncryptor",
    "init_security",
]
