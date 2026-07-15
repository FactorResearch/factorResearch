# Phase 8 Recovery Evidence

**Status:** Backup and restore tooling hardened; production restore and regional cutover drills remain open.
**Evidence date:** 2026-07-14

## Implemented

- Three authoritative PostgreSQL stores are streamed directly from `pg_dump` into AES-256 encrypted archives.
- Backup files become visible only after a nonempty encrypted stream completes.
- The encryption passphrase is read from the environment rather than exposed in process arguments.
- Restore tests stream decrypted archives directly into isolated scratch databases.
- Restore errors are fatal and scratch databases are removed on every handled failure path.
- Disposable Redis queues/caches are recovered from authoritative PostgreSQL state or recomputed.
- Repository tests enforce the no-plaintext and cleanup contracts.

## Open Certification Evidence

- [ ] Store backups in immutable, geographically separate object storage using independently managed keys.
- [ ] Run restore drills against sanitized production-size archives and record measured RPO/RTO.
- [ ] Verify row counts, constraints, recent writes, encrypted fields, and application journeys after restore.
- [ ] Restore after a deliberately bad migration and execute regional cutover/return.
- [ ] Obtain operations and security sign-off on drill evidence and key access.

Successful backup commands are not recovery proof. Certification remains blocked until timed restore and cutover evidence exists.
