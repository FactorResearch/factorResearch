# Production-Grade Proof Plan

**Created:** 2026-07-14  
**Scope:** Cenvarnweb application, workers, databases, Redis, external providers, financial models, authentication, billing, deployment, and operations.  
**Purpose:** Produce repeatable evidence that the system is safe, correct, performant, recoverable, and operable under realistic production conditions.

This document is the release-proof authority. `README.md`, `SECURITY_CHECKLIST.md`, `AUTHENTICATION_SETUP.md`, `Publish.md`, `AGENCY_AUDIT.md`, and country release documents remain implementation references.

## Proof Standard

A control is complete only when all four exist:

1. An automated test, repeatable drill, or independent assessment.
2. A measurable acceptance threshold defined before execution.
3. A dated artifact containing configuration, results, and failures.
4. A named owner who signs the result and remediation decision.

Passing unit tests alone is not production proof. Tests must run against a production-equivalent staging environment using the same process model, dependencies, network boundaries, migration path, and managed services as production.

## Required Environments

### Isolated Environments

- Development, CI, staging, production, and disaster-recovery environments use separate credentials, databases, Redis instances, encryption keys, Auth0 applications, Stripe modes, analytics projects, and storage.
- Staging mirrors production runtime versions, Gunicorn configuration, worker topology, TLS termination, proxy headers, database extensions, Redis policies, and provider limits.
- CI and staging cannot reach production data or secrets.
- Synthetic production tests use dedicated monitored accounts and tagged records.
- Infrastructure and configuration changes are versioned and reviewable.

### Reproducible Release

- Pin Python and JavaScript dependencies and record runtime versions.
- Build one immutable release artifact and promote the same artifact through staging and production.
- Generate an SBOM and checksums for every release.
- Record Git commit, migration version, asset version, configuration schema version, and model algorithm versions.
- Provide a one-command staging deployment and a documented production promotion command.

## Phase 0: Ownership and Baselines

**Goal:** Establish the operating contract before stress or security testing.

### Work

- Name owners for application, infrastructure, database, security, privacy, financial-model integrity, incident command, and release approval.
- Define service tier, expected concurrent users, daily analyses, portfolio sizes, screener traffic, background-job volume, and provider budgets.
- Capture current staging latency, throughput, CPU, memory, database connections, Redis operations, payload size, and error rate.
- Inventory every process, route, callback, worker, queue, scheduled task, database, cache, provider, secret, webhook, and public endpoint.
- Classify data by public, internal, personal, financial, credential, and regulated sensitivity.

### Exit Evidence

- `artifacts/production-proof/00-baseline/architecture.md`
- Data-flow and trust-boundary diagram.
- Dependency/service inventory with owners.
- Approved capacity assumptions and initial risk register.

## Phase 1: Release and Test Integrity

**Goal:** Prove that every release is reproducible and fails closed when required checks fail.

### Required CI Gates

- Full Python suite, not a selected subset.
- Python compilation and import smoke test with startup enabled and disabled.
- SCSS build and generated-asset consistency check.
- JavaScript tests and linting for clientside callbacks and service worker behavior.
- Database tests against supported PostgreSQL versions.
- Redis-backed integration tests plus explicit Redis-outage tests.
- Browser smoke tests for all primary routes in Chromium, Firefox, and WebKit.
- WCAG 2.2 AA automated audit for desktop, tablet, and mobile viewports.
- Security scans defined in Phase 5.
- Migration upgrade and rollback verification.
- Changed-code coverage threshold and critical-module coverage floor.

### Acceptance Gates

- Zero failed or quarantined release-blocking tests.
- No flaky critical-path test across 20 consecutive CI runs.
- Critical modules maintain at least 90% branch coverage; repository coverage cannot decrease without approval.
- A clean checkout can build and run using documented commands.
- Production artifact contains no test data, debug mode, source secrets, or development-only feature flags.

## Phase 2: Performance and Capacity Proof

**Goal:** Determine safe capacity and prove graceful behavior beyond it.

### Workloads

- Warm cached stock analysis.
- Cold stock analysis requiring SEC/provider retrieval.
- Five rapid analyses from one mobile session.
- Many users analyzing the same ticker to validate singleflight behavior.
- Many users analyzing different tickers to validate provider and database limits.
- Screener search, filter, pagination, and quick peek.
- Portfolio CRUD, simulation, comparison, and maximum supported holdings.
- Factor Lab backtests, including maximum universe and history.
- Chart expansion and repeated chart-cache access.
- Authentication, subscription lookup, usage accounting, and Stripe webhook bursts.
- Background refresh and foreground traffic running simultaneously.

### Test Types

- Baseline: one user, warm and cold paths.
- Load: expected peak for at least 60 minutes.
- Stress: increase traffic until the first defined bottleneck.
- Spike: move from idle to 2x expected peak within 10 seconds.
- Soak: expected peak for 12 hours and normal traffic for 72 hours.
- Recovery: return to normal load after saturation without restart.

### Initial Service-Level Objectives

Thresholds must be adjusted after the baseline and approved before certification.

| Path | p50 | p95 | p99 | Error rate |
|---|---:|---:|---:|---:|
| Cached page/API response | 250 ms | 750 ms | 1.5 s | < 0.1% |
| Cached stock analysis | 500 ms | 1.5 s | 3 s | < 0.5% |
| Cold stock analysis | 3 s | 10 s | 20 s | < 1%, excluding declared provider outage |
| Screener interaction | 200 ms | 600 ms | 1.2 s | < 0.1% |
| Portfolio simulation | 1 s | 4 s | 8 s | < 0.5% |
| Background queue delay | 5 s | 30 s | 120 s | no lost jobs |

### Resource Gates

- CPU remains below 70% sustained at expected peak.
- Memory reaches a stable plateau during soak; growth is below 2% after warm-up.
- Database pool wait p95 is below 100 ms and never exhausts at expected peak.
- Database connections remain within the approved server budget across all workers.
- Redis memory, command latency, and connection count remain bounded.
- Provider concurrency never exceeds configured limits, including after timeout.
- Queue depth drains to baseline within 10 minutes after a 2x spike.
- No unbounded thread, lock, cache-key, file-descriptor, or connection growth.
- Graceful overload returns `429` or `503` with retry guidance instead of hanging.

### Tools and Artifacts

- Use k6 or Locust for versioned workloads.
- Capture server metrics, traces, database statistics, Redis statistics, and provider-call counts for every run.
- Store workload source, environment manifest, test data size, raw results, charts, bottleneck analysis, and signed capacity envelope.

## Phase 3: Reliability and Failure Injection

**Goal:** Prove bounded degradation and automatic recovery when dependencies fail.

### Failure Scenarios

- Redis unavailable at startup and during active requests.
- PostgreSQL unavailable, slow, read-only, connection-exhausted, and restarted mid-transaction.
- Individual provider timeout, rate limit, invalid response, schema change, and prolonged outage.
- DNS failure and outbound network partition.
- Worker crash during analysis and during job acknowledgement.
- Gunicorn worker termination during requests.
- Queue poison message and repeated job failure.
- Cache directory absent, read-only, full, and corrupted.
- Encryption key missing, invalid, and rotated.
- Auth0/JWKS unavailable or returning stale keys.
- Stripe webhook duplicated, reordered, delayed, and forged.
- Clock skew and daylight-saving transition.
- Partial deployment with mixed application versions.

### Acceptance Gates

- No cross-user data leakage or authorization bypass under any failure.
- No committed partial financial record after transaction failure.
- Retriable jobs are idempotent and eventually complete or enter a visible dead-letter queue.
- Circuit breakers open, recover, and report health correctly.
- Required production infrastructure fails closed where documented.
- Optional integrations degrade without taking down core analysis.
- Recovery occurs without manual process restart unless the runbook declares one necessary.
- Every failure emits an actionable metric/log/trace with correlation ID and no secret data.

## Phase 4: Data and Financial-Model Integrity

**Goal:** Prove that results are reproducible, traceable, and safe across data changes.

### Controls

- Maintain golden datasets for normal companies, banks, insurers, negative-equity companies, missing filings, restatements, splits, mergers, foreign issuers, and malformed provider data.
- Independently calculate representative outputs for every production model.
- Property-test invariants, numeric boundaries, `None`, NaN, infinity, zero denominators, negative values, and extreme magnitudes.
- Verify currency, units, fiscal periods, amendments, duplicate concepts, filing precedence, and split adjustments.
- Record source document, filing date, retrieval date, normalization version, model version, and cache provenance.
- Prove every production model has a UI/API consumer or an explicit background-only designation.
- Prove every new model backfills already-analyzed database stocks.
- Compare model outputs before and after every algorithm change and require approved tolerance bands.
- Validate point-in-time backtests and prominently label any remaining look-ahead or survivorship bias.

### Acceptance Gates

- 100% of production models are registered, versioned, surfaced, tested, and backfill-capable.
- Golden outputs match independently approved values within documented tolerances.
- No silent coercion of missing data into a favorable score.
- A result can be reproduced from its recorded source and algorithm version.
- Data freshness and provenance are visible for every analysis.

## Phase 5: Security Verification

**Goal:** Produce layered automated and independent evidence against realistic threats.

### Automated Security Program

- SAST for Python and JavaScript.
- Dependency vulnerability scanning with lockfile enforcement.
- Secret scanning across Git history and release artifacts.
- SBOM generation and container/runtime image scanning where applicable.
- DAST against authenticated and unauthenticated staging flows.
- API and input fuzzing for ticker, portfolio, callback, route, query, and webhook inputs.
- Security-header, TLS, cookie, CORS, CSP, CSRF, host-header, and trusted-proxy validation.
- IaC/configuration scanning when deployment configuration is versioned.
- License-policy scanning for dependencies and market-data sources.

### Manual Review

- Authentication lifecycle, session fixation, logout, token validation, JWKS rotation, and account linking.
- Authorization and tenant isolation across portfolios, custom analyses, usage, billing, snapshots, and caches.
- IDOR, injection, XSS, SSRF, path traversal, request smuggling, open redirect, and unsafe deserialization.
- Rate-limit bypass across workers, proxies, user identities, and IP rotation.
- Stripe webhook signature, replay protection, idempotency, and subscription-state transitions.
- Secret storage, rotation, least privilege, break-glass access, and audit logging.
- Encryption at rest and in transit, including backup copies and key rotation.
- Privacy consent, analytics opt-out, retention, deletion, and data export.
- Administrative access and production support tooling.

### Independent Assessment

- External penetration test covering anonymous, authenticated, premium, billing, and administrative surfaces.
- Remediate all critical/high findings and retest them.
- Document accepted medium/low risks with owner and expiration date.
- Repeat annually and after major authentication, payment, or architecture changes.

### Release Gates

- Zero open critical or high exploitable vulnerabilities.
- No known cross-tenant access path.
- No secret present in source, logs, client payloads, or release artifact.
- Production refuses insecure authentication, encryption, rate-limit, and proxy configurations.

## Phase 6: Privacy and Compliance Proof

**Goal:** Demonstrate that collected data has a lawful, minimal, and enforceable lifecycle.

### Controls

- Maintain a data inventory and processing-purpose register.
- Define retention and deletion schedules for accounts, portfolios, events, logs, backups, waitlists, and billing references.
- Verify privacy-policy and terms versions are recorded at consent where required.
- Test analytics opt-out before any optional event leaves the application.
- Test user export, account deletion, backup expiration, and provider deletion requests.
- Define incident notification and breach-response obligations for operating jurisdictions.
- Complete vendor reviews and data-processing agreements for Auth0, Stripe, hosting, analytics, email, error reporting, and market-data providers.
- Verify market-data licenses permit storage, display, caching, derived calculations, backups, and each launch jurisdiction.

### Acceptance Gates

- Every stored field has an owner, purpose, retention period, and deletion mechanism.
- Deletion drills prove active systems are cleared immediately and backups expire within policy.
- Nonessential analytics are consented to and opt-out is verified end to end.
- Legal and data-license approval is recorded before public release.

## Phase 7: Observability and Operational Readiness

**Goal:** Ensure operators detect, diagnose, and resolve failures before users report them.

### Telemetry

- Structured logs with request/job correlation IDs and redaction.
- Metrics for request latency/error/traffic/saturation, analysis stages, cache hit rates, provider calls, circuit states, database pools, Redis, queues, workers, model failures, and billing webhooks.
- Distributed traces across web request, job dispatch, provider call, database work, and result persistence.
- Frontend real-user monitoring for Web Vitals, JavaScript errors, navigation, and mobile viewport failures.
- Synthetic checks for login, analysis, screener, portfolio, billing, and health endpoints.

### Alerts

- Alerts map to an owner, severity, runbook, and actionable threshold.
- Alert on SLO burn rate, not isolated noise.
- Test paging delivery and escalation quarterly.
- Detect missing telemetry as an incident.
- Avoid personal, financial, token, cookie, or provider-secret content in telemetry.

### Runbooks

- Database outage and pool exhaustion.
- Redis outage and rate-limit consistency.
- Provider outage/rate limiting.
- Queue backlog/dead letters.
- Authentication outage/JWKS rotation.
- Stripe webhook delay or replay.
- Bad model/data release.
- Cache corruption/disk exhaustion.
- Secret compromise and key rotation.
- Rollback, traffic disablement, and emergency read-only mode.

### Acceptance Gates

- On-call can identify the failed dependency from dashboards within five minutes.
- Every critical alert is exercised in staging.
- Mean time to acknowledge is below five minutes during drills.
- Runbooks are executable by an engineer who did not write them.

## Phase 8: Backup, Restore, and Disaster Recovery

**Goal:** Prove recovery from data loss and regional/service failure.

### Required Decisions

- Approve Recovery Point Objective and Recovery Time Objective for market data, user data, analytics, caches, and configuration.
- Define which caches are disposable and which records are authoritative.
- Encrypt backups with independently managed keys and restricted access.
- Define backup retention, immutability, geographic separation, and deletion behavior.

### Drills

- Restore each PostgreSQL database into an isolated environment from backup.
- Verify schema, row counts, referential integrity, recent writes, encrypted fields, and application behavior.
- Restore after a deliberately bad migration.
- Recover Redis/queues according to their declared durability contract.
- Rebuild the service from source, artifact repository, secrets manager, and backups only.
- Execute a full disaster-recovery cutover and return-to-primary drill.

### Acceptance Gates

- Measured RPO and RTO meet approved targets.
- Restore success is demonstrated, not inferred from backup-job success.
- No production credentials are exposed to the drill environment.
- Results, timing, gaps, and remediation are signed and retained.

## Phase 9: Deployment, Migration, and Rollback Proof

**Goal:** Make releases boring, observable, and reversible.

### Controls

- Backward-compatible expand/migrate/contract database changes.
- Migration tested against empty, representative, and production-size restored databases.
- Migration lock duration and disk growth measured.
- Pre-deploy backup and automated preflight configuration validation.
- Canary or staged rollout with health and SLO comparison.
- Graceful worker shutdown and queue draining.
- Automatic rollback criteria for error rate, latency, health, and business-integrity checks.
- Feature flags for high-risk models and data providers.
- Version compatibility documented for rolling deployments.

### Acceptance Gates

- Staging promotion and rollback complete within the approved release window.
- Failed migration leaves the previous release operational or follows a tested restore path.
- No mixed-version data corruption during rolling deployment.
- Release artifact, approvals, migration output, smoke tests, and rollback decision are archived.

## Phase 10: User Experience and Accessibility Proof

**Goal:** Prove the native-feeling experience under real devices and constrained conditions.

### Matrix

- Current and previous major Chromium, Firefox, and Safari/WebKit.
- iOS Safari and Android Chrome on representative low-, mid-, and high-tier devices.
- Desktop, tablet, and mobile orientations.
- Light, dark, high-contrast, reduced-motion, 200% zoom, and keyboard-only use.
- Slow 3G/4G, high latency, intermittent connectivity, offline shell, and expired service-worker cache.

### Acceptance Gates

- WCAG 2.2 AA automated and manual keyboard/screen-reader checks pass.
- No horizontal overflow or inaccessible controls at supported widths and 200% zoom.
- Core Web Vitals meet “good” thresholds at the 75th percentile on mobile.
- Five-stock rapid-analysis workflow is usable without navigation loss or blocking layout shift.
- Errors, loading, stale data, and offline states are understandable and recoverable.

## Phase 11: Incident Response and Game Days

**Goal:** Prove the organization can respond, not merely the software.

### Program

- Define severity levels, incident commander role, communications, escalation, evidence preservation, and customer notification.
- Maintain security, privacy, availability, data-integrity, and provider-outage playbooks.
- Run quarterly game days covering one availability and one security/data scenario.
- Conduct blameless post-incident reviews with tracked corrective actions.
- Test contact lists, status-page updates, legal escalation, and vendor escalation.

### Acceptance Gates

- Participants meet communication, containment, recovery, and evidence targets.
- Every action has an owner and due date.
- Repeated drill findings block release until systemic causes are addressed.

## Final Production Certification Gate

Public launch or major scale increase requires all of the following:

- Full CI and production-equivalent staging suite green.
- Approved capacity envelope with load, stress, spike, and soak evidence.
- Reliability fault matrix passed or risks explicitly accepted.
- Financial-model golden set and provenance checks approved.
- Zero open critical/high security findings and external penetration retest complete.
- Privacy, licensing, and vendor approvals complete.
- Dashboards, alerts, synthetic checks, and on-call runbooks exercised.
- Backup restore and disaster-recovery drill meet RPO/RTO.
- Deployment, migration, canary, and rollback drills passed.
- WCAG 2.2 AA and supported-device matrix passed.
- Security, engineering, operations, model-integrity, privacy/legal, and product owners sign the release record.

## Continuous Proof After Launch

| Frequency | Required proof |
|---|---|
| Every commit | Unit/integration tests, lint/compile, SAST, secret and dependency scans |
| Every release | Full suite, migration test, staging smoke/load check, SBOM, canary, rollback readiness |
| Daily | Synthetic journeys, backups, vulnerability feed, certificate/domain checks |
| Weekly | SLO review, database/Redis capacity, queue/dead-letter review, provider budget review |
| Monthly | Access review, dependency updates, restore sample, cost/capacity forecast |
| Quarterly | Restore drill, game day, paging test, privacy deletion sample, key-rotation sample |
| Annually | External penetration test, full DR exercise, threat-model review, vendor/license review |

## Evidence Layout

Do not commit secrets or sensitive production exports. Store sanitized reports or references under:

```text
artifacts/production-proof/
  00-baseline/
  01-release-integrity/
  02-performance/
  03-reliability/
  04-model-integrity/
  05-security/
  06-privacy/
  07-observability/
  08-recovery/
  09-deployment/
  10-ux-accessibility/
  11-incidents/
  release-signoff/
```

Each report must include date, commit, artifact checksum, environment, sanitized configuration, test version, data volume, start/end time, raw-result location, pass/fail decision, deviations, owner, and approval.

## Recommended Execution Order

1. Complete Phase 0 and approve SLO/RPO/RTO targets.
2. Make Phase 1 CI gates mandatory.
3. Implement Phase 7 telemetry before load and failure testing.
4. Run Phases 2 and 3, then fix bottlenecks and repeat until stable.
5. Complete model-integrity, security, and privacy proof in Phases 4-6.
6. Execute recovery, deployment, browser, and incident drills in Phases 8-11.
7. Assemble the final release evidence and obtain all signoffs.

No phase is complete because controls merely exist in code. Completion requires the recorded proof and acceptance decision defined above.
