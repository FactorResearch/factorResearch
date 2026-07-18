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
