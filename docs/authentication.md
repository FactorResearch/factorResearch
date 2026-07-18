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

The current lifecycle store is process-local because the optional PostgreSQL
connection is not guaranteed during startup. A multi-worker production rollout
must provide a shared revocation store before enabling this interface across
workers. Tokens, authorization headers, refresh credentials, and raw provider
responses must not be logged.

Security boundary: provider verification is the external trust boundary;
`TokenService` owns first-party token claims and lifecycle; endpoint and
portfolio services remain responsible for resource ownership, usage limits,
and capability/entitlement checks.
