# Phase 3 Reliability Evidence

**Status:** Core ownership and outage controls implemented; managed-service fault injection remains open.  
**Evidence date:** 2026-07-14

## Implemented

- Production web workers cannot own background schedulers or analysis consumers.
- Procfile declares a dedicated `analysis-worker` process role.
- Production analysis enqueue fails closed when Redis durability is unavailable; development retains bounded local fallback.
- Redis reconnects after a bounded cooldown instead of remaining disabled for process lifetime.
- Analysis jobs move atomically to an in-flight list, acknowledge only after completion, and are recovered on sole-worker startup; crashes no longer silently drop dequeued work.
- Provider timeout permits, circuit state, pool transactions, cache failures, webhook signatures, and encryption failures have regression coverage elsewhere in the full suite.

## Required Staging Failure Matrix

- [ ] Redis unavailable at startup, interrupted during work, restored, and queue reconciled.
- [ ] PostgreSQL slow, unavailable, restarted, read-only, and pool-exhausted.
- [ ] Provider timeout, rate limit, malformed schema, DNS failure, and prolonged outage.
- [ ] Worker termination before/during/after queue acknowledgement.
- [ ] Gunicorn worker termination and rolling mixed-version deployment.
- [ ] Cache absent, read-only, full, and corrupt.
- [ ] Auth0/JWKS outage and signing-key rotation.
- [ ] Stripe duplicate, reordered, delayed, and forged webhooks.
- [ ] Encryption key missing, invalid, and rotated.
- [ ] Recovery signals and runbooks exercised for every scenario.

Certification requires raw fault-injection timelines proving no cross-user leak, no partial committed record, visible dead letters, actionable telemetry, and recovery without undeclared restart.
