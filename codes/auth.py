"""
Authentication module for Intrinsic IQ.

Supports Auth0, Clerk, and Supabase Auth as managed authentication providers.
Injects authenticated user_id into all callbacks and enforces secure cookie policies.

Environment variables required:
  AUTH_PROVIDER:          "auth0" | "clerk" | "supabase"
  AUTH0_DOMAIN:           Your Auth0 domain (e.g., myapp.auth0.com)
  AUTH0_CLIENT_ID:        Auth0 application client ID
  AUTH0_CLIENT_SECRET:    Auth0 application client secret
  CLERK_PUBLIC_KEY:       Clerk public key (for local dev token validation)
  CLERK_ISSUER:           Expected Clerk token issuer
  CLERK_AUDIENCE:         Expected Clerk token audience
  SUPABASE_URL:           Supabase project URL
  SUPABASE_API_KEY:       Supabase anon/public key
  SUPABASE_JWT_AUDIENCE:  Expected Supabase token audience (default: authenticated)
  CALLBACK_URL:           Callback URL for auth provider redirects
"""

import os
import secrets
import requests
from functools import wraps
from datetime import datetime, timedelta
from urllib.parse import urlencode

import jwt
from jwt.exceptions import PyJWTError

# Import Flask and related libraries
import flask
from flask import redirect, request, session, url_for
from codes.core.config import is_production


# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

AUTH_PROVIDER = os.environ.get("AUTH_PROVIDER", "").strip().lower() or None
CALLBACK_URL = os.environ.get("CALLBACK_URL", "http://localhost:8050/callback")

# Auth0 Configuration
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.environ.get("AUTH0_CLIENT_SECRET")

# Clerk Configuration
CLERK_PUBLIC_KEY = os.environ.get("CLERK_PUBLIC_KEY")
CLERK_ISSUER = os.environ.get("CLERK_ISSUER")
CLERK_AUDIENCE = os.environ.get("CLERK_AUDIENCE")

# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_API_KEY = os.environ.get("SUPABASE_API_KEY")
SUPABASE_JWT_AUDIENCE = os.environ.get("SUPABASE_JWT_AUDIENCE", "authenticated")

# Cache for verified tokens (to reduce external API calls)
_token_cache: dict[str, tuple[str, datetime]] = {}
TOKEN_CACHE_TTL = 3600  # 1 hour

# Cache for remote JWKS documents
_jwks_cache: dict[str, tuple[dict, datetime]] = {}
_JWKS_CACHE_TTL = 3600  # 1 hour
GENERIC_AUTH_ERROR = "Authentication failed. Please try again."
AUTH0_OAUTH_STATE_KEY = "_auth0_oauth_state"
DEV_PERSONA_SESSION_KEY = "_dev_persona"
DEV_PERSONAS = {
    "free": {
        "user_id": "dev-free-user",
        "plan": "trial",
        "status": "trialing",
        "label": "Free / Trial",
    },
    "paid": {
        "user_id": "dev-paid-user",
        "plan": "premium",
        "status": "active",
        "label": "Paid / Premium",
    },
    "pro": {
        "user_id": "dev-pro-user",
        "plan": "professional",
        "status": "active",
        "label": "Pro / Professional",
    },
}


def _auth_error_response(status_code: int = 400):
    """Return a safe, structured authentication error that remains keyboard-readable."""
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Authentication error | FactorResearch</title><link rel="stylesheet" href="/assets/error_pages.css"><link rel="stylesheet" href="/assets/accessibility.css"></head>
<body class="error-page"><a class="skip-link" href="#main-content">Skip to main content</a>
<main id="main-content" class="error-shell" tabindex="-1"><section class="error-card" role="alert">
<h1>Authentication error</h1><p>{GENERIC_AUTH_ERROR}</p><a class="primary-action" href="/login">Try signing in again</a>
</section></main></body></html>"""
    return flask.Response(body, status=status_code, mimetype="text/html")


# ──────────────────────────────────────────────────────────────────────────────
# Token Verification (Provider-Agnostic)
# ──────────────────────────────────────────────────────────────────────────────

def _get_cached_user_id(token: str) -> str | None:
    """Check if token is in cache and still valid."""
    if token in _token_cache:
        user_id, expiry = _token_cache[token]
        if datetime.utcnow() < expiry:
            return user_id
        else:
            del _token_cache[token]
    return None


def _cache_user_id(token: str, user_id: str) -> None:
    """Cache the user_id for this token."""
    _token_cache[token] = (user_id, datetime.utcnow() + timedelta(seconds=TOKEN_CACHE_TTL))


def _fetch_jwks(jwks_url: str) -> dict | None:
    cached = _jwks_cache.get(jwks_url)
    if cached:
        jwks, expiry = cached
        if datetime.utcnow() < expiry:
            return jwks

    try:
        resp = requests.get(jwks_url, timeout=5)
        resp.raise_for_status()
        jwks = resp.json()
        _jwks_cache[jwks_url] = (jwks, datetime.utcnow() + timedelta(seconds=_JWKS_CACHE_TTL))
        return jwks
    except Exception as e:
        print(f"[AUTH] Failed to fetch JWKS from {jwks_url}: {e}")
        return None


def _decode_jwt(token: str, jwks_url: str, audience: str | None = None, issuer: str | None = None) -> dict | None:
    try:
        unverified_header = jwt.get_unverified_header(token)
        jwks = _fetch_jwks(jwks_url)
        if not jwks or "keys" not in jwks:
            return None
        key = next((k for k in jwks["keys"] if k.get("kid") == unverified_header.get("kid")), None)
        if key is None:
            return None
        options = {"verify_aud": audience is not None}
        return jwt.decode(
            token,
            jwt.PyJWK.from_dict(key).key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options=options,
        )
    except (PyJWTError, ValueError) as e:
        print(f"[AUTH] JWT verification failed: {e}")
        return None


def verify_token(token: str) -> str | None:
    """
    Verify JWT token and return authenticated user_id.
    
    Returns:
        Authenticated user_id if token is valid, None otherwise.
    """
    if not token:
        return None

    # Check cache first
    cached_user_id = _get_cached_user_id(token)
    if cached_user_id:
        return cached_user_id
    
    if AUTH_PROVIDER == "auth0":
        user_id = _verify_auth0_token(token)
    elif AUTH_PROVIDER == "clerk":
        user_id = _verify_clerk_token(token)
    elif AUTH_PROVIDER == "supabase":
        user_id = _verify_supabase_token(token)
    else:
        print("[AUTH] No authentication provider configured")
        return None

    if user_id:
        _cache_user_id(token, user_id)
    return user_id


def _verify_auth0_token(token: str) -> str | None:
    """Verify Auth0 JWT token."""
    if not AUTH0_DOMAIN or not AUTH0_CLIENT_ID or not AUTH0_CLIENT_SECRET:
        print("[AUTH] Auth0 credentials not configured")
        return None

    token = token.strip()
    if token.count(".") == 2:
        issuer = f"https://{AUTH0_DOMAIN}/"
        jwks_url = f"{issuer}.well-known/jwks.json"
        payload = _decode_jwt(token, jwks_url, audience=AUTH0_CLIENT_ID, issuer=issuer)
        if payload:
            user_id = payload.get("sub") or payload.get("user_id")
            if user_id:
                return user_id

    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"https://{AUTH0_DOMAIN}/userinfo", headers=headers, timeout=5)
        if resp.status_code == 200:
            user_info = resp.json()
            user_id = user_info.get("sub") or user_info.get("user_id")
            return user_id
    except Exception as e:
        print(f"[AUTH] Auth0 token verification failed: {e}")

    return None


def _verify_clerk_token(token: str) -> str | None:
    """Verify Clerk JWT token."""
    if not CLERK_PUBLIC_KEY or not CLERK_ISSUER or not CLERK_AUDIENCE:
        print("[AUTH] Clerk token verification is not fully configured")
        return None

    try:
        payload = jwt.decode(
            token,
            CLERK_PUBLIC_KEY,
            algorithms=["RS256"],
            audience=CLERK_AUDIENCE,
            issuer=CLERK_ISSUER,
        )
        user_id = payload.get("sub") or payload.get("user_id")
        return user_id
    except PyJWTError as e:
        print(f"[AUTH] Clerk token verification failed: {e}")
    return None


def _verify_supabase_token(token: str) -> str | None:
    """Verify Supabase JWT token."""
    if not SUPABASE_URL:
        print("[AUTH] Supabase URL not configured")
        return None

    token = token.strip()
    if token.count(".") == 2:
        jwks_url = SUPABASE_URL.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        payload = _decode_jwt(
            token,
            jwks_url,
            audience=SUPABASE_JWT_AUDIENCE,
            issuer=SUPABASE_URL.rstrip("/") + "/auth/v1",
        )
        if payload:
            user_id = payload.get("sub") or payload.get("user_id") or payload.get("id")
            if user_id:
                return user_id

    if not SUPABASE_API_KEY:
        print("[AUTH] Supabase API key not configured for fallback verification")
        return None

    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "apikey": SUPABASE_API_KEY,
        }
        resp = requests.get(
            f"{SUPABASE_URL.rstrip('/')}/auth/v1/user",
            headers=headers,
            timeout=5,
        )
        if resp.status_code == 200:
            user_info = resp.json()
            return user_info.get("id")
    except Exception as e:
        print(f"[AUTH] Supabase token verification failed: {e}")
    return None


def _is_dev_mode() -> bool:
    return not is_production()


def get_dev_persona() -> dict | None:
    if not _is_dev_mode():
        return None
    if not flask.has_request_context():
        return None
    key = session.get(DEV_PERSONA_SESSION_KEY)
    if not key:
        return None
    persona = DEV_PERSONAS.get(str(key))
    if not persona:
        session.pop(DEV_PERSONA_SESSION_KEY, None)
        return None
    return {"key": str(key), **persona}


def set_dev_persona(persona_key: str) -> dict:
    if not _is_dev_mode():
        raise RuntimeError("Developer personas are disabled in production.")
    key = str(persona_key or "").strip().lower()
    if key not in DEV_PERSONAS:
        raise KeyError(key)
    session[DEV_PERSONA_SESSION_KEY] = key
    return {"key": key, **DEV_PERSONAS[key]}


def clear_dev_persona() -> None:
    session.pop(DEV_PERSONA_SESSION_KEY, None)


def get_dev_subscription_override() -> dict | None:
    persona = get_dev_persona()
    if not persona:
        return None
    return {
        "user_id": persona["user_id"],
        "plan": persona["plan"],
        "status": persona["status"],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Session Management
# ──────────────────────────────────────────────────────────────────────────────

def get_authenticated_user_id() -> str | None:
    """
    Get authenticated user_id from Flask session.
    
    Returns:
        Authenticated user_id if session is valid, None otherwise.
    """
    # Every explicit Bearer request goes through the unified first-party
    # lifecycle first. An invalid or revoked Bearer token must never fall back
    # to a cookie identity, which would make API authorization inconsistent.
    bearer = request.headers.get("Authorization", "")
    if bearer.lower().startswith("bearer "):
        from codes.api.auth import request_identity

        identity = request_identity()
        if identity:
            return identity.user_id
        token = bearer[7:].strip()
        user_id = verify_token(token)
        if user_id:
            # Provider tokens are exchanged into the existing browser session
            # for compatibility; the credential itself is never persisted.
            set_authenticated_user(user_id)
        return user_id

    persona = get_dev_persona()
    if persona:
        return persona["user_id"]

    if "_authenticated_user_id" in session:
        return session.get("_authenticated_user_id")

    return None


def set_authenticated_user(user_id: str) -> None:
    """Store only the nonsecret authenticated user ID in the client session."""
    session["_authenticated_user_id"] = user_id


def clear_authenticated_user() -> None:
    """Clear authentication from session."""
    session.pop("_authenticated_user_id", None)
    session.pop("_auth_token", None)
    clear_dev_persona()


# ──────────────────────────────────────────────────────────────────────────────
# Decorators
# ──────────────────────────────────────────────────────────────────────────────

def require_auth(f):
    """
    Decorator to require authentication for a Flask route or Dash callback.
    
    Usage:
        @require_auth
        def my_callback(...):
            user_id = get_authenticated_user_id()
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_authenticated_user_id()
        if not user_id:
            if AUTH_PROVIDER == "auth0":
                if request.is_json or "application/json" in request.headers.get("Accept", ""):
                    return {"error": "Unauthorized"}, 401
                return redirect(url_for("auth_login"))
            return {"error": "Unauthorized"}, 401
        return f(*args, **kwargs)
    return decorated_function


# ──────────────────────────────────────────────────────────────────────────────
# Auth0 OAuth Flow (Example - can be adapted for Clerk/Supabase)
# ──────────────────────────────────────────────────────────────────────────────

def setup_auth0_routes(app_server):
    """
    Register Auth0 OAuth routes with Flask server.
    
    Registers:
      /login       - Initiates Auth0 login
      /callback    - OAuth callback (redirects from Auth0)
      /logout      - Clears session and redirects to Auth0 logout
    """
    if AUTH_PROVIDER != "auth0":
        return
    
    if not AUTH0_DOMAIN or not AUTH0_CLIENT_ID or not AUTH0_CLIENT_SECRET:
        print("[AUTH] Auth0 routes not registered: missing configuration")
        return
    
    @app_server.route("/login")
    def auth_login():
        """Redirect to Auth0 login."""
        state = secrets.token_urlsafe(32)
        session[AUTH0_OAUTH_STATE_KEY] = state
        auth0_authorize_url = f"https://{AUTH0_DOMAIN}/authorize"
        params = {
            "client_id": AUTH0_CLIENT_ID,
            "redirect_uri": CALLBACK_URL,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
        }
        return redirect(f"{auth0_authorize_url}?{urlencode(params)}")
    
    @app_server.route("/callback")
    def auth_callback():
        """Handle Auth0 OAuth callback."""
        code = request.args.get("code")
        error = request.args.get("error")
        returned_state = request.args.get("state")
        expected_state = session.pop(AUTH0_OAUTH_STATE_KEY, None)
        
        if error:
            print("[AUTH] Callback received provider error")
            return _auth_error_response(400)

        if not expected_state or not returned_state or not secrets.compare_digest(expected_state, returned_state):
            print("[AUTH] Callback rejected invalid OAuth state")
            return _auth_error_response(400)
        
        if not code:
            return _auth_error_response(400)
        
        # Exchange code for token
        try:
            token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
            payload = {
                "client_id": AUTH0_CLIENT_ID,
                "client_secret": AUTH0_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": CALLBACK_URL,
            }
            response = requests.post(token_url, json=payload, timeout=10)
            
            if response.status_code != 200:
                print(f"[AUTH] Token exchange failed with status {response.status_code}")
                return _auth_error_response(400)
            
            token_data = response.json()
            access_token = token_data.get("access_token")
            
            # Verify and store user info
            user_id = verify_token(access_token)
            if user_id:
                set_authenticated_user(user_id)
                return redirect("/")  # Redirect to app
        except Exception as e:
            print(f"[AUTH] Callback error type: {type(e).__name__}")
            return _auth_error_response(500)
        
        return _auth_error_response(400)
    
    @app_server.route("/logout")
    def auth_logout():
        """Logout: clear session and redirect to Auth0 logout."""
        clear_authenticated_user()
        auth0_logout_url = f"https://{AUTH0_DOMAIN}/v2/logout"
        params = {
            "client_id": AUTH0_CLIENT_ID,
            "returnTo": "http://localhost:8050/",
        }
        return redirect(f"{auth0_logout_url}?{urlencode(params)}")
    
    print(f"[AUTH] Auth0 routes registered (domain={AUTH0_DOMAIN})")


# ──────────────────────────────────────────────────────────────────────────────
# Secure Cookie Configuration
# ──────────────────────────────────────────────────────────────────────────────

def configure_secure_cookies(app_server):
    """
    Configure Flask session to use secure cookies as per ISSUE_008.
    
    Sets:
      Secure=true       (HTTPS only)
      HttpOnly=true     (No JavaScript access)
      SameSite=Lax|Strict (CSRF protection)
    """
    production = is_production()
    
    app_server.config.update(
        SESSION_COOKIE_SECURE=production,  # HTTPS only in production
        SESSION_COOKIE_HTTPONLY=True,  # Never expose to JavaScript
        SESSION_COOKIE_SAMESITE="Lax",  # CSRF protection (use "Strict" if no cross-site forms)
        SESSION_COOKIE_NAME="intrinsic_iq_session",  # Explicit cookie name
        PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
        SESSION_REFRESH_EACH_REQUEST=True,  # Refresh session on each request
    )
    
    @app_server.before_request
    def make_session_permanent():
        """Mark session as permanent to enforce lifetime."""
        session.permanent = True
    
    secure_str = "Secure" if production else "insecure (dev mode)"
    print(f"[AUTH] Secure cookies configured ({secure_str})")


# ──────────────────────────────────────────────────────────────────────────────
# Initialization
# ──────────────────────────────────────────────────────────────────────────────

def init_auth(app_server):
    """
    Initialize authentication for the Flask server.
    
    Configures:
      - Secure cookies
      - Auth provider routes (Auth0)
      - Token caching
    
    Usage in app.py:
        from codes.auth import init_auth, get_authenticated_user_id
        
        app = dash.Dash(...)
        server = app.server
        init_auth(server)
        
        # In callbacks:
        user_id = get_authenticated_user_id()
    """
    print(f"\n[AUTH] Initializing authentication (provider={AUTH_PROVIDER})")

    if is_production() and not AUTH_PROVIDER:
        raise RuntimeError("AUTH_PROVIDER must be configured in production.")

    configure_secure_cookies(app_server)

    # Register the provider-neutral API lifecycle once. Provider-specific
    # login remains available for browser compatibility, while all first-party
    # API clients can use the same exchange, refresh, and logout contract.
    from codes.api.auth import auth_api

    if "auth_api" not in app_server.blueprints:
        app_server.register_blueprint(auth_api)

    @app_server.route("/dev/impersonate", methods=["GET"])
    def dev_impersonate():
        if not _is_dev_mode():
            return {"error": "Not found"}, 404
        persona_key = (request.args.get("persona") or "").strip().lower()
        if persona_key in {"", "clear", "none"}:
            clear_dev_persona()
            return {"ok": True, "persona": None, "available": sorted(DEV_PERSONAS)}
        try:
            persona = set_dev_persona(persona_key)
        except KeyError:
            return {
                "error": f"Unknown persona '{persona_key}'",
                "available": sorted(DEV_PERSONAS),
            }, 400
        return {"ok": True, "persona": persona, "available": sorted(DEV_PERSONAS)}

    if AUTH_PROVIDER == "auth0":
        setup_auth0_routes(app_server)

    print("[AUTH] Authentication initialized\n")
