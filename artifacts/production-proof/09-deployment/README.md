# Phase 9 Deployment Evidence

**Status:** Release preflight and graceful worker shutdown implemented; production-size migration, canary, and rollback drills remain open.
**Evidence date:** 2026-07-14

## Implemented

- The platform release phase validates production configuration before touching a database.
- Schema initialization is idempotent and runs outside web/worker startup through a dedicated release command.
- Workers handle `SIGTERM`/`SIGINT`, stop accepting queue work, and use bounded polling for prompt shutdown.
- Queue acknowledgement leaves interrupted work recoverable on the next worker start.
- The release procedure defines immutable evidence, staged traffic, automatic rollback thresholds, and post-release checks.
- Tests enforce release ordering and cooperative shutdown.

## Open Certification Evidence

- [ ] Time migrations on empty, representative, and sanitized production-size restored databases.
- [ ] Measure lock duration, disk growth, and mixed-version behavior for every schema change.
- [ ] Execute staged production-equivalent canary and rollback within the approved window.
- [ ] Archive the artifact digest, migration output, synthetic results, approvals, and traffic decision.
- [ ] Prove a deliberately failed migration leaves the prior release operational or meets tested restore RTO.
