# Authentication Implementation (ISSUE_008)

## Overview

ISSUE_008 has been implemented with full managed authentication support for Auth0, Clerk, and Supabase Auth. The implementation includes:

- ✅ Managed authentication provider integration (Auth0, Clerk, Supabase Auth)
- ✅ Stable authenticated user_id injected into all callbacks  
- ✅ Secure cookie configuration (Secure=true, HttpOnly=true, SameSite=Lax|Strict)
- ✅ Per-user session isolation for portfolio and analysis data
- ✅ Token caching for performance (1-hour TTL)
- ✅ Backward compatibility with session-based UUID for local development

## Architecture

### Files Modified/Created

1. **`codes/auth.py`** (NEW)
   - Manages authentication with multiple provider support
   - Handles token verification and caching
   - Configures secure cookies
   - Provides decorator and utility functions

2. **`codes/app.py`** (MODIFIED)
   - Initialized auth system on startup
   - Replaced `_session_id()` with `_get_user_id()`
   - All callbacks now use authenticated user_id
   - Secure cookie configuration applied

3. **`codes/requirements.txt`** (MODIFIED)
   - Added `python-jose[cryptography]` for JWT verification
   - Added `flask-session` for session management

## Configuration

### Environment Variables

Choose ONE authentication provider and set the corresponding environment variables:

#### Auth0 Configuration

```bash
export AUTH_PROVIDER="auth0"
export AUTH0_DOMAIN="your-domain.auth0.com"
export AUTH0_CLIENT_ID="your_client_id"
export AUTH0_CLIENT_SECRET="your_client_secret"
export CALLBACK_URL="https://yourapp.com/callback"
export FLASK_ENV="production"
```

**Auth0 Setup:**
1. Create an Auth0 account and application at https://auth0.com
2. In Auth0 dashboard:
   - Go to Applications > Your App > Settings
   - Set "Allowed Callback URLs" to `https://yourapp.com/callback`
   - Set "Allowed Logout URLs" to `https://yourapp.com/`
   - Copy Client ID and Client Secret
3. Your domain is shown at the top of the Settings page

#### Clerk Configuration

```bash
export AUTH_PROVIDER="clerk"
export CLERK_PUBLIC_KEY="your_public_key"
export CALLBACK_URL="https://yourapp.com/callback"
```

**Clerk Setup:**
1. Create account at https://clerk.com
2. In Clerk dashboard:
   - Go to API Keys
   - Copy your Publishable Key (public key)
   - Configure redirect URIs in your Clerk app settings
3. Clerk handles OAuth flows automatically

#### Supabase Auth Configuration

```bash
export AUTH_PROVIDER="supabase"
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_API_KEY="your_anon_key"
export CALLBACK_URL="https://yourapp.com/callback"
```

**Supabase Setup:**
1. Create project at https://supabase.com
2. In Supabase dashboard:
   - Go to Settings > API
   - Copy Project URL and anon key
   - Go to Authentication > Providers
   - Configure OAuth providers (Google, GitHub, etc.)
3. Set redirect URL in provider settings

### Local Development (No Auth Required)

For local development without an auth provider:

```bash
# Don't set AUTH_PROVIDER or leave it unset
# App will use session-based UUIDs automatically
python codes/app.py
```

**Warning:** In production, authentication MUST be configured. The fallback to session UUIDs is **for development only**.

## Usage

### In Callbacks

All callbacks now automatically receive authenticated user_id:

```python
from codes import auth

@callback(...)
def my_callback(...):
    # Get authenticated user_id (or session UUID in dev mode)
    user_id = auth.get_authenticated_user_id()
    
    # Pass to portfolio/analysis functions
    portfolios = portfolio_engine.list_portfolios(user_id)
    ...
```

### Route Protection

Protect Flask routes with the `@require_auth` decorator:

```python
from codes.auth import require_auth

@server.route("/api/my-endpoint")
@require_auth
def protected_endpoint():
    user_id = auth.get_authenticated_user_id()
    return {"user_id": user_id}
```

### Login/Logout (Auth0 Only)

Auth0 provides automatic OAuth routes:

- `/login` - Redirect to Auth0 login
- `/callback` - Auth0 callback handler (automatic)
- `/logout` - Clear session and redirect to Auth0 logout

## Security Features

### Secure Cookies

All session cookies are configured with:

| Setting | Value | Purpose |
|---------|-------|---------|
| `Secure=true` | HTTPS only | Prevents transmission over HTTP |
| `HttpOnly=true` | No JavaScript access | Prevents XSS cookie theft |
| `SameSite=Lax` | CSRF protection | Requires same-site form submission |
| `Session Lifetime` | 30 days | Automatic expiration |

### Token Caching

Tokens are cached in memory for 1 hour to:
- Reduce external API calls to auth provider
- Improve performance
- Stale tokens are automatically evicted

### Per-User Data Isolation

All user data is scoped by user_id:
- Portfolios: `{user_id}_p_{portfolio_name}`
- Portfolio index: `{user_id}_index`
- Session cache: keyed by user_id

## Production Deployment

### Pre-Launch Checklist

- [ ] Choose authentication provider (Auth0, Clerk, or Supabase)
- [ ] Create provider account and application
- [ ] Set environment variables in production deployment
- [ ] Enable HTTPS (required for `Secure=true` cookies)
- [ ] Configure domain/callback URLs in auth provider
- [ ] Test login/logout flows
- [ ] Verify secure cookies are set (check browser dev tools)
- [ ] Set `FLASK_ENV=production` to enforce HTTPS-only cookies

### Deployment Examples

#### Docker Compose with Auth0

```yaml
services:
  graham-app:
    environment:
      AUTH_PROVIDER: auth0
      AUTH0_DOMAIN: your-domain.auth0.com
      AUTH0_CLIENT_ID: ${AUTH0_CLIENT_ID}
      AUTH0_CLIENT_SECRET: ${AUTH0_CLIENT_SECRET}
      CALLBACK_URL: https://yourapp.com/callback
      FLASK_ENV: production
```

#### Railway/Heroku with Auth0

```bash
heroku config:set AUTH_PROVIDER=auth0
heroku config:set AUTH0_DOMAIN=your-domain.auth0.com
heroku config:set AUTH0_CLIENT_ID=xxx
heroku config:set AUTH0_CLIENT_SECRET=xxx
heroku config:set CALLBACK_URL=https://yourapp.herokuapp.com/callback
heroku config:set FLASK_ENV=production
```

## API Reference

### `auth.get_authenticated_user_id() -> Optional[str]`

Get authenticated user_id from Flask session.

**Returns:** Authenticated user_id if available, None otherwise

**Usage:**
```python
user_id = auth.get_authenticated_user_id()
if user_id:
    portfolios = portfolio_engine.list_portfolios(user_id)
```

### `auth.verify_token(token: str) -> Optional[str]`

Verify a JWT token with the configured provider.

**Parameters:**
- `token`: JWT access token

**Returns:** User ID if token is valid, None otherwise

### `auth.set_authenticated_user(user_id: str, token: str = "") -> None`

Store authenticated user information in Flask session.

**Parameters:**
- `user_id`: Authenticated user identifier
- `token`: Optional JWT token for future verification

### `auth.clear_authenticated_user() -> None`

Remove authentication from current session.

**Usage:** Called in logout handlers

### `auth.init_auth(app_server) -> None`

Initialize authentication for Flask server.

Must be called once during app startup:

```python
from codes import auth
import dash

app = dash.Dash(...)
auth.init_auth(app.server)
```

### `@auth.require_auth` Decorator

Protect Flask routes to require authentication.

```python
from codes.auth import require_auth

@server.route("/api/protected")
@require_auth
def protected_route():
    user_id = auth.get_authenticated_user_id()
    return {"user": user_id}
```

## Testing

### Local Development Test

```bash
cd /home/amin/Downloads/graham-app

# Install dependencies
pip install -r codes/requirements.txt

# Run app (uses session-based UUIDs)
python codes/app.py

# Visit http://localhost:8050
# App should work with portfolio operations
```

### Auth0 Test

```bash
export AUTH_PROVIDER="auth0"
export AUTH0_DOMAIN="your-domain.auth0.com"
export AUTH0_CLIENT_ID="your_client_id"
export AUTH0_CLIENT_SECRET="your_client_secret"
export CALLBACK_URL="http://localhost:8050/callback"

python codes/app.py

# Visit http://localhost:8050/login
# You should be redirected to Auth0
```

### Verify Secure Cookies

1. Open browser developer tools (F12)
2. Go to Application > Cookies > http://localhost:8050
3. Check for `intrinsic_iq_session` cookie
4. Properties should show:
   - HttpOnly: ✓
   - Secure: ✓ (in production)
   - SameSite: Lax

## Acceptance Criteria (ISSUE_008)

- ✅ Every callback receives a stable, authenticated user_id
- ✅ Session cookies meet secure_cookie_config requirements:
  - ✅ Secure=true (HTTPS only)
  - ✅ HttpOnly=true (no JavaScript access)
  - ✅ SameSite=Lax|Strict (CSRF protection)
- ✅ Per-user session isolation maintained
- ✅ Backward compatible with local development
- ✅ Configurable for Auth0, Clerk, Supabase Auth
- ✅ Token caching for performance
- ✅ No raw exceptions or secrets in logs/UI

## Troubleshooting

### "Auth provider not configured"

**Problem:** Auth routes not being registered

**Solution:** Set `AUTH_PROVIDER` and provider-specific credentials in environment

### "Token verification failed"

**Problem:** Auth provider returned error

**Solution:** 
1. Verify credentials are correct
2. Check callback URL matches provider settings
3. Ensure token hasn't expired
4. Check provider API is reachable

### Cookies not being set

**Problem:** Session cookies not appearing in browser

**Solution:**
1. In dev: Use `http://localhost:8050` (HTTP is OK for dev)
2. In production: Ensure HTTPS is enabled
3. Set `FLASK_ENV=production` or check `app.debug` is False
4. Verify `SESSION_COOKIE_SECURE` is set correctly

### Session lost after page refresh

**Problem:** User logs out after refresh

**Solution:**
1. Check `PERMANENT_SESSION_LIFETIME` is set (default: 30 days)
2. Ensure `session.permanent = True` in `before_request`
3. Verify cookies are being sent in requests

## Migration from Old Session System

The old `_session_id()` function has been completely replaced. To ensure smooth migration:

1. All existing user portfolios keyed with old session UUIDs will be orphaned
2. Users will need to recreate portfolios after authentication is deployed
3. Consider running a migration script to preserve portfolios by mapping old UUIDs to new user IDs

If you need to preserve old session data, implement a migration:

```python
# Map old session UUIDs to new user IDs
old_uid = flask.session.get("_uid_old")
new_uid = auth.get_authenticated_user_id()
if old_uid and new_uid:
    # Copy old portfolio data to new user_id
    portfolio_engine.migrate_portfolios(old_uid, new_uid)
```

## Next Steps

1. **ISSUE_009**: Implement billing/subscription enforcement
2. **ISSUE_007**: Migrate to PostgreSQL with proper user_id scoping
3. **Continuous**: Set up error monitoring (Sentry) and dependency scanning
