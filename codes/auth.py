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
  SUPABASE_URL:           Supabase project URL
  SUPABASE_API_KEY:       Supabase anon/public key
  CALLBACK_URL:           Callback URL for auth provider redirects
"""

import os
import json
import requests
from functools import wraps
from typing import Optional, Tuple
from datetime import datetime, timedelta

# Import Flask and related libraries
import flask
from flask import redirect, request, session, url_for


# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

AUTH_PROVIDER = os.environ.get("AUTH_PROVIDER", "auth0").lower()
CALLBACK_URL = os.environ.get("CALLBACK_URL", "http://localhost:8050/callback")

# Auth0 Configuration
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.environ.get("AUTH0_CLIENT_SECRET")

# Clerk Configuration
CLERK_PUBLIC_KEY = os.environ.get("CLERK_PUBLIC_KEY")

# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_API_KEY = os.environ.get("SUPABASE_API_KEY")

# Cache for verified tokens (to reduce external API calls)
_token_cache: dict[str, Tuple[str, datetime]] = {}
TOKEN_CACHE_TTL = 3600  # 1 hour


# ──────────────────────────────────────────────────────────────────────────────
# Token Verification (Provider-Agnostic)
# ──────────────────────────────────────────────────────────────────────────────

def _get_cached_user_id(token: str) -> Optional[str]:
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


def verify_token(token: str) -> Optional[str]:
    """
    Verify JWT token and return authenticated user_id.
    
    Returns:
        Authenticated user_id if token is valid, None otherwise.
    """
    # Check cache first
    cached_user_id = _get_cached_user_id(token)
    if cached_user_id:
        return cached_user_id
    
    if AUTH_PROVIDER == "auth0":
        return _verify_auth0_token(token)
    elif AUTH_PROVIDER == "clerk":
        return _verify_clerk_token(token)
    elif AUTH_PROVIDER == "supabase":
        return _verify_supabase_token(token)
    else:
        print(f"[AUTH] Unknown provider: {AUTH_PROVIDER}")
        return None


def _verify_auth0_token(token: str) -> Optional[str]:
    """Verify Auth0 JWT token."""
    if not AUTH0_DOMAIN or not AUTH0_CLIENT_ID or not AUTH0_CLIENT_SECRET:
        print("[AUTH] Auth0 credentials not configured")
        return None
    
    try:
        # Auth0 tokens are verified via the userinfo endpoint
        # For production, use a JWT library like python-jose
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"https://{AUTH0_DOMAIN}/userinfo", headers=headers, timeout=5)
        
        if resp.status_code == 200:
            user_info = resp.json()
            user_id = user_info.get("sub") or user_info.get("user_id")
            if user_id:
                _cache_user_id(token, user_id)
                return user_id
    except Exception as e:
        print(f"[AUTH] Auth0 token verification failed: {e}")
    
    return None


def _verify_clerk_token(token: str) -> Optional[str]:
    """Verify Clerk JWT token."""
    if not CLERK_PUBLIC_KEY:
        print("[AUTH] Clerk public key not configured")
        return None
    
    try:
        # For production, use python-jose to verify JWT
        # This is a simplified example
        import json
        import base64
        
        # Parse JWT (simplified - no signature verification in this stub)
        parts = token.split(".")
        if len(parts) != 3:
            return None
        
        # Decode payload (add padding if needed)
        payload_b64 = parts[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        
        payload = json.loads(base64.b64decode(payload_b64))
        user_id = payload.get("sub") or payload.get("user_id")
        
        if user_id:
            _cache_user_id(token, user_id)
            return user_id
    except Exception as e:
        print(f"[AUTH] Clerk token verification failed: {e}")
    
    return None


def _verify_supabase_token(token: str) -> Optional[str]:
    """Verify Supabase JWT token."""
    if not SUPABASE_URL or not SUPABASE_API_KEY:
        print("[AUTH] Supabase credentials not configured")
        return None
    
    try:
        # Verify token via Supabase API
        headers = {
            "Authorization": f"Bearer {token}",
            "apikey": SUPABASE_API_KEY,
        }
        resp = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers=headers,
            timeout=5
        )
        
        if resp.status_code == 200:
            user_info = resp.json()
            user_id = user_info.get("id")
            if user_id:
                _cache_user_id(token, user_id)
                return user_id
    except Exception as e:
        print(f"[AUTH] Supabase token verification failed: {e}")
    
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Session Management
# ──────────────────────────────────────────────────────────────────────────────

def get_authenticated_user_id() -> Optional[str]:
    """
    Get authenticated user_id from Flask session.
    
    Returns:
        Authenticated user_id if session is valid, None otherwise.
    """
    if "_authenticated_user_id" in session:
        return session.get("_authenticated_user_id")
    
    # Try to extract from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user_id = verify_token(token)
        if user_id:
            session["_authenticated_user_id"] = user_id
            session["_auth_token"] = token
            return user_id
    
    return None


def set_authenticated_user(user_id: str, token: str = "") -> None:
    """Store authenticated user_id in Flask session."""
    session["_authenticated_user_id"] = user_id
    if token:
        session["_auth_token"] = token


def clear_authenticated_user() -> None:
    """Clear authentication from session."""
    session.pop("_authenticated_user_id", None)
    session.pop("_auth_token", None)


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
            # For API routes, return 401 Unauthorized
            if request.is_json or "application/json" in request.headers.get("Accept", ""):
                return {"error": "Unauthorized"}, 401
            # For browser routes, redirect to login
            return redirect(url_for("auth_login"))
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
        auth0_authorize_url = f"https://{AUTH0_DOMAIN}/authorize"
        params = {
            "client_id": AUTH0_CLIENT_ID,
            "redirect_uri": CALLBACK_URL,
            "response_type": "code",
            "scope": "openid profile email",
        }
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return redirect(f"{auth0_authorize_url}?{query_string}")
    
    @app_server.route("/callback")
    def auth_callback():
        """Handle Auth0 OAuth callback."""
        code = request.args.get("code")
        error = request.args.get("error")
        
        if error:
            return f"Login failed: {error}", 400
        
        if not code:
            return "Missing authorization code", 400
        
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
                return f"Token exchange failed: {response.text}", 400
            
            token_data = response.json()
            access_token = token_data.get("access_token")
            
            # Verify and store user info
            user_id = verify_token(access_token)
            if user_id:
                set_authenticated_user(user_id, access_token)
                return redirect("/")  # Redirect to app
        except Exception as e:
            print(f"[AUTH] Callback error: {e}")
            return f"Authentication failed: {e}", 500
        
        return "Authentication failed", 400
    
    @app_server.route("/logout")
    def auth_logout():
        """Logout: clear session and redirect to Auth0 logout."""
        clear_authenticated_user()
        auth0_logout_url = f"https://{AUTH0_DOMAIN}/v2/logout"
        params = {
            "client_id": AUTH0_CLIENT_ID,
            "returnTo": "http://localhost:8050/",
        }
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return redirect(f"{auth0_logout_url}?{query_string}")
    
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
    # Determine if running in production (no debug mode)
    is_production = not app_server.debug or os.environ.get("FLASK_ENV") == "production"
    
    app_server.config.update(
        SESSION_COOKIE_SECURE=is_production,  # HTTPS only in production
        SESSION_COOKIE_HTTPONLY=True,  # Never expose to JavaScript
        SESSION_COOKIE_SAMESITE="Lax",  # CSRF protection (use "Strict" if no cross-site forms)
        SESSION_COOKIE_NAME="intrinsic_iq_session",  # Explicit cookie name
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),  # Session expiry
        SESSION_REFRESH_EACH_REQUEST=True,  # Refresh session on each request
    )
    
    @app_server.before_request
    def make_session_permanent():
        """Mark session as permanent to enforce lifetime."""
        session.permanent = True
    
    secure_str = "Secure" if is_production else "insecure (dev mode)"
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
    
    # Configure secure cookies
    configure_secure_cookies(app_server)
    
    # Setup provider-specific routes
    setup_auth0_routes(app_server)
    
    print("[AUTH] Authentication initialized\n")
