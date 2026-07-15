# Initial Production Risk Register

Scoring uses likelihood and impact from 1 (low) to 5 (critical). Score is their product. Risks at 15 or above block certification unless independently accepted with an expiry date.

| ID | Risk | L | I | Score | Existing control | Required closure evidence | Owner |
|---|---|---:|---:|---:|---|---|---|
| R-001 | Multiple web workers start duplicate schedulers/job consumers | 4 | 4 | 16 | Redis queue and bounded workers | Multi-worker fault/load test; dedicated process or proven leader election | Operations |
| R-002 | Provider outage or timeout exhausts threads/quotas | 3 | 5 | 15 | timeouts, semaphores, circuits, singleflight | spike/failure injection with bounded threads and recovery | Engineering |
| R-003 | DB pool budget exceeds managed PostgreSQL connection limit | 4 | 4 | 16 | bounded per-process pools | worker-count budget plus pool saturation test | Data platform |
| R-004 | Redis outage removes cross-worker session/rate/job guarantees | 3 | 5 | 15 | production fail-closed controls in selected paths | startup/runtime outage matrix and recovery evidence | Operations/Security |
| R-005 | Financial source normalization silently changes a score | 3 | 5 | 15 | model tests and source-specific normalization | golden dataset, provenance, differential release gate | Model integrity |
| R-006 | Cross-user portfolio/custom-analysis access | 2 | 5 | 10 | identity-bound queries and authorization tests | authenticated DAST/IDOR test and penetration retest | Security |
| R-007 | Bad migration locks or corrupts production data | 3 | 5 | 15 | release migration command | production-size clone timing, rollback/restore drill | Data platform |
| R-008 | Backup exists but cannot restore within business needs | 3 | 5 | documented backup expectations | measured restore and full DR drill | Operations |
| R-009 | Secret or sensitive record leaks through logs/client telemetry | 3 | 5 | redaction/generic errors | log corpus scan, DAST, manual security review | Security/Privacy |
| R-010 | Stripe duplicate/reordered webhook corrupts entitlement | 3 | 4 | signature checks and subscription service | replay/order/idempotency integration tests | Payments |
| R-011 | Unlicensed data is stored/displayed in a launch jurisdiction | 3 | 5 | country release documentation | written license/legal approval and deletion drill | Privacy/Legal |
| R-012 | Mobile layout/performance prevents rapid analysis workflow | 3 | 3 | responsive UI and accessibility tests | real-device/Web Vitals workflow matrix | Product/UX |
| R-013 | In-process caches/locks/connections grow during long uptime | 2 | 4 | bounded/TTL caches and pools | 72-hour soak with stable memory/descriptors | Engineering |
| R-014 | Authentication provider/JWKS outage creates unsafe fallback | 2 | 5 | production auth requirement and token validation | outage/key-rotation tests proving fail-closed behavior | Security |
| R-015 | Insufficient telemetry delays detection and diagnosis | 4 | 4 | basic performance/error metrics | dashboards, burn-rate alerts, trace and game-day evidence | Operations |

## Review Rules

- Review weekly during certification and monthly after launch.
- Add newly discovered risks immediately; never renumber existing IDs.
- Closure requires a linked evidence artifact, not a code-change reference alone.
- Accepted risks record approver, rationale, compensating control, and expiration.
