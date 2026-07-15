# Initial Capacity and Service Assumptions

**Status:** Conservative planning envelope; not proven capacity. Phase 2 must validate or revise it before certification.

## Launch Workload Envelope

| Dimension | Normal | Expected peak | Certification stress target |
|---|---:|---:|---:|
| Concurrent active users | 25 | 100 | 200 |
| HTTP/callback requests per second | 5 | 25 | 50 |
| Stock analyses per minute | 10 | 50 | 100 |
| Concurrent cold analyses | 2 | 8 | 16 |
| Same-ticker concurrent requests | 5 | 50 | 100 |
| Screener rows | 5,000 | 10,000 | 20,000 |
| Holdings per portfolio | 25 | 100 | documented hard maximum |
| Concurrent simulations | 2 | 10 | 20 |
| Analysis jobs queued | 50 | 500 | 2,000 spike |
| Previously analyzed symbols | 5,000 | 20,000 | 50,000 |

## Initial SLO Inputs

- Monthly availability target: 99.9% for core read and cached-analysis paths.
- Cached page/API p95: 750 ms; cached analysis p95: 1.5 seconds.
- Cold analysis p95: 10 seconds, excluding declared upstream outage windows.
- Core request error rate: below 0.1%; cold-analysis error rate below 1% outside provider incidents.
- Queue delay p95: below 30 seconds and no lost acknowledged jobs.
- Mobile Core Web Vitals: “good” at the 75th percentile.

## Resource Guardrails

- Sustained CPU below 70% and memory plateau after warm-up.
- Database pool wait p95 below 100 ms with no expected-peak exhaustion.
- Total database connections remain below 70% of managed-server capacity.
- Redis command p95 below 10 ms and memory below 70% of configured maximum.
- Provider concurrency never exceeds configured semaphore limits.
- Queue drains from the certification spike within 10 minutes.

## Provider Budget Assumptions

- SEC traffic remains below published/courtesy limits and uses a monitored production identity.
- Finnhub, Tiingo, and Alpha Vantage budgets are deployment-tier inputs, not constants inferred from documentation.
- Phase 2 tests use provider stubs for scale and a separately approved low-volume live-provider validation.
- Load tests must never consume production provider quotas or violate provider terms.

## Open Decisions

- Select Gunicorn worker/thread count after connection-budget and load evidence.
- Establish an explicit maximum holdings count and reject larger requests before simulation.
- Decide whether Redis analysis jobs require stronger durability/acknowledgement semantics.
- Move scheduler/job consumers to dedicated processes if multi-worker testing confirms duplicate ownership.
- Approve final RPO/RTO in Phase 8.
