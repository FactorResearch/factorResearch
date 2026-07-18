# Unified authentication (ISSUE_066)

`codes.api.auth.TokenService` is the first-party authentication boundary for
API clients. A provider Bearer token is exchanged at `POST /api/auth/token` for
a 15-minute access token and a 30-day refresh token. Access tokens are signed
with `AUTH_TOKEN_SECRET` (falling back to the Flask secret outside production)
and contain only the user ID, session family ID, token ID, issuer, and bounded
timestamps.

Refresh tokens rotate at `POST /api/auth/refresh`. The presented refresh token
is immediately marked unusable; replay of a previously used refresh token
revokes its complete session family. `POST /api/auth/logout` revokes the
current family. Explicit Bearer requests never fall back to a browser cookie,
so browser, mobile, and service clients receive the same identity evaluation.

Lifecycle records use the configured Redis instance under `auth:session:*` and
`auth:revoked-token:*`, with TTLs matching the token expiry. This makes session
revocation and refresh-token replay detection consistent across workers. In
production, missing or unavailable Redis fails authentication operations closed;
non-production services may use the process-local fallback for development and
tests. Tokens, authorization headers, refresh credentials, and raw provider
responses must not be logged.

Security boundary: provider verification is the external trust boundary;
`TokenService` owns first-party token claims and lifecycle; endpoint and
portfolio services remain responsible for resource ownership, usage limits,
and capability/entitlement checks.
