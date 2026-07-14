# Phase 7 Observability Evidence

**Status:** Telemetry and operational response contract implemented; external export, dashboards, tracing, RUM, and drills remain open.
**Evidence date:** 2026-07-14

## Implemented

- Bounded request RED window using route templates, method, status class, and latency.
- Sanitized/generated `X-Request-ID` on every response.
- Existing analysis latency/cache/failure metrics retained in a structured process snapshot.
- Aggregate provider circuit, component cache, analysis queue/dead-letter, and database-pool health.
- Protected `/_internal/performance` endpoint requiring `INTERNAL_METRICS_TOKEN`.
- Tests for bounded metric cardinality, route privacy, request-ID sanitization, and pool utilization.
- Versioned alert catalog with severity, owner, threshold, and runbook mappings.
- Executable runbooks for every declared critical dependency and emergency control.
- Synthetic journey definitions for health, analysis, screener, portfolio, authentication, and billing.
- Repository tests that reject missing alert owners, thresholds, or runbook targets.

## Open Certification Evidence

- [ ] Export metrics to the selected production monitoring backend.
- [ ] Add distributed traces across request, analysis job, provider, and persistence boundaries.
- [ ] Add frontend RUM/Web Vitals and JavaScript error reporting with consent/redaction.
- [ ] Create SLO, provider, pool, Redis, queue, billing, and model-failure dashboards.
- [ ] Install the alert catalog in the selected monitoring backend.
- [ ] Exercise every critical alert and paging escalation in staging.
- [ ] Prove an uninvolved engineer can diagnose injected failures within five minutes.

The in-process window supports diagnosis and test assertions but is not a durable multi-worker metrics backend. Production certification requires aggregation outside the application process.
