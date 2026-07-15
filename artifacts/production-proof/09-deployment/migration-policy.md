# Migration Compatibility Policy

- Use expand, migrate, contract: add compatible structures, backfill asynchronously, switch readers/writers, then remove old structures in a later release.
- Every migration is idempotent and safe when web and worker versions overlap.
- New code must tolerate old rows; old code must tolerate newly added nullable/defaulted fields.
- Large backfills must be bounded, resumable, observable, and excluded from the release transaction.
- Table rewrites, long exclusive locks, destructive drops, and type narrowing require production-size timing and explicit data-platform approval.
- A release must not claim rollback capability when its schema is incompatible with the previous artifact.
