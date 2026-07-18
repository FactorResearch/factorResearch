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
