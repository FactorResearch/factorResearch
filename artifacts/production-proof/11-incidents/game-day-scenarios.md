# Game-Day Scenarios

## Availability: Database Saturation During Market Open

- Inject pool saturation and delayed queries in production-equivalent staging while synthetic analysis and portfolio traffic runs.
- Pass: alert fires, SEV-2 is declared and acknowledged within 5 minutes, dependency is identified within 5 minutes, unsafe writers are paused, service recovers without cross-user or partial-write defects, and updates meet cadence.
- Record alert/paging timestamps, dashboard path, commands/decisions, queue effects, recovery time, synthetic results, and corrective actions.

## Security/Data: Leaked Provider Credential and Corrupt Prices

- Inject a revoked test provider credential plus plausible but incorrect prices into an isolated provider response.
- Pass: exposure is declared SEV-1, credential is revoked/rotated, circuit/model controls prevent new incorrect results, affected snapshots are identified by provenance, customer/legal decision is recorded, and clean data is restored without erasing evidence.
- Record detection, containment, affected-population query, key-rotation verification, golden-set comparison, communications decision, and recovery time.

For both scenarios, an observer who did not write the runbook operates the procedure. Every gap receives an owner and due date; repeat findings block release.
