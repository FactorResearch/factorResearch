# Purpose
Ensure local, test, staging, and production environments are explicit, validated, secure, and reproducible.
# Core rules
- Centralize configuration access.
- Validate all required configuration at startup.
- Do not read environment variables throughout arbitrary modules.
- Secrets must never be committed, printed, or embedded in frontend bundles.
- Environment differences must be intentional and documented.
# Environment model
Define local, test, staging, and production with clear service endpoints, databases, providers, feature flags, logging, and safety restrictions.
# Configuration schema
Every setting must define:
- Name.
- Type.
- Required status.
- Default, if safe.
- Secret classification.
- Allowed values.
- Owning subsystem.
- Restart requirements.

`AUTH_TOKEN_SECRET` is the sensitive security setting used to sign first-party
API access and refresh tokens. It must be at least 32 characters in production.
Rotating it requires coordinated session invalidation and rollout because
existing signed tokens will no longer validate after rotation.

`DATABASE_USERS_URL` is the normal application credential for tenant-owned
records. In production its PostgreSQL role must not be a superuser or have
`BYPASSRLS`. `DATABASE_USERS_SERVICE_URL` is a separate restart-required secret
for Stripe reconciliation, waitlist, privacy erasure, and controlled service
workflows. Rotate either through the deployment secret manager; never expose
migration or service URLs to clients or logs.

`DATABASE_MARKET_WORKER_URL` is the restart-required market-worker credential.
Production processes labelled `analysis-worker`, `canada-ingest-worker`,
`market-worker`, or `sec-worker` require it and must not receive users, service,
or migration URLs. Web and worker market URLs must use distinct PostgreSQL LOGIN
principals with membership in `cenvarn_app` and `cenvarn_market_worker`
respectively. Environment-specific blue/green LOGIN names are allowed; startup
verifies canonical membership rather than a hard-coded login name.

Canonical role provisioning, grants, ownership, no-downtime rotation, emergency
revocation, and monitoring are defined in
`docs/issue-082-postgresql-role-operations.md`.
# Feature flags
Flags require owner, purpose, rollout plan, default behavior, telemetry, expiry date, and removal issue.
# Reproducibility
Use lockfiles, documented setup, seeded test data, and automated environment validation.
# AI implementation requirements
The AI must add configuration through the central schema and must not introduce scattered environment access or unsafe defaults.

## ISSUE_045 runtime service

`codes.services.configuration.ConfigurationService` is the typed runtime
boundary for environment-backed operational settings. Each setting declares its
parser, ownership, secret classification, default, and lifecycle policy.

The service keeps an immutable in-process snapshot and refreshes it after its
short cache TTL. A candidate reload is validated completely before activation;
invalid values never replace the last valid snapshot. Settings marked as
hot-reloadable are activated immediately. Restart-required changes remain in
the active snapshot's `pending_restart` list until the process is restarted.

Audit output is redacted: it records the actor, action, setting names, and
outcome, never raw values or credentials. The service keeps prior valid
snapshots in memory so operators can perform a controlled rollback within the
process lifetime. Administrative reload and rollback endpoints, if added,
must enforce server-side authorization and should write the audit file to a
durable, access-controlled operational location.
