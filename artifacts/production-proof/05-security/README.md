# Phase 5 Security Evidence

**Status:** Automated and configuration controls implemented; DAST and independent penetration assessment remain open.  
**Evidence date:** 2026-07-14

## Automated Controls

- Full security regression suite on every PR through the release gate.
- Weekly and PR secret scanning, Bandit SAST, pip/npm vulnerability audits, and Python SBOM generation.
- Production preflight rejects missing/weak session secrets, invalid Fernet keys, wildcard hosts, non-PostgreSQL databases, non-TLS Redis, insecure base URLs, incomplete authentication/billing, internal feature flags, development CSRF bypass, and placeholder SEC identity.
- Network-hermetic tests prevent accidental credentialed calls from CI.
- Existing controls cover CSRF/same-origin checks, trusted hosts, secure cookies, security headers, output sanitization, signed Stripe webhooks, authorization ownership, rate limits, and encrypted sensitive cache data.

## Threat Priorities

1. Cross-user IDOR across portfolios, custom analyses, usage, and subscriptions.
2. Authentication token/state/JWKS manipulation and unsafe outage fallback.
3. Stripe replay, ordering, signature, and entitlement reconciliation.
4. XSS/injection through provider data, ticker/company names, and Dash callbacks.
5. SSRF/path traversal through provider, logo, cache, and route inputs.
6. Rate-limit bypass across workers/proxies and Redis failure.
7. Secrets or personal data in logs, analytics, client payloads, backups, or artifacts.

## Open Release Blockers

- [ ] Authenticated DAST covering anonymous, free, premium, billing, and account deletion flows.
- [ ] Fuzz callback, route, provider, webhook, and file/cache inputs.
- [ ] Validate TLS, CSP, headers, cookies, CORS, proxies, and hosts on deployed staging.
- [ ] Independent penetration test and retest of all critical/high findings.
- [ ] Production access/least-privilege review and secret-rotation drill.
- [ ] License and market-data security/vendor reviews.

Release requires zero open critical/high exploitable findings. Accepted lower risks require owner, rationale, compensating control, and expiry.
