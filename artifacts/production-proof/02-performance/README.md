# Phase 2 Performance Evidence

**Status:** Workload and pass/fail tooling implemented; production-equivalent staging execution remains open.  
**Evidence date:** 2026-07-14

## Implemented

- Versioned Locust workload covering screener, legal/static navigation, varied ticker analysis, and same-ticker pressure.
- Explicit baseline, peak, stress, spike, 12-hour soak, and 72-hour soak profiles.
- Machine-readable evaluator for aggregate p95 and failure-rate thresholds.
- Operational endpoint exposes request, provider, queue, cache, and pool signals needed during tests.
- Portfolio requests are bounded by the existing 10-holding hard maximum.

## Local Harness Result

`local-smoke-verdict.json` records a successful two-worker localhost smoke run. It validates Locust execution, CSV production, and threshold evaluation only. It is not included in the production capacity decision.

## Required Staging Evidence

- [ ] Immutable release commit and environment manifest.
- [ ] Raw Locust CSV/HTML output and machine-readable verdict for every profile.
- [ ] CPU, memory, threads, descriptors, database pools, Redis, queues, and provider concurrency timelines.
- [ ] Approved capacity ceiling and Gunicorn worker/thread configuration.
- [ ] Stable memory after warm-up and no unbounded resource growth.
- [ ] Recovery to baseline within ten minutes after spike/stress saturation.
- [ ] Provider-stub proof that concurrency and quota controls remain bounded.
- [ ] Separately approved low-volume live-provider validation.
- [ ] Capture authenticated Dash callback payloads for actual analysis execution, portfolio simulation/comparison, and Factor Lab workloads using synthetic staging accounts.

No production capacity claim is valid until these staging artifacts exist.
