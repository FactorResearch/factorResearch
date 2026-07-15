# Authentication Failure

1. Confirm Auth0 status, application callback configuration, JWKS retrieval, token validation errors, and clock skew.
2. Preserve existing valid sessions unless compromise is suspected. Never bypass signature, issuer, or audience checks.
3. Disable account-changing operations if identity integrity cannot be established.
4. For key rotation, refresh JWKS through the normal cache path and test a dedicated identity.
5. Escalate immediately for token acceptance across users, leaked credentials, or unauthorized access.
6. Verify login, refresh, logout, and protected-route denial before restoring full traffic.
