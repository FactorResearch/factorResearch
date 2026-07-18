# Operational modes and health controller (ISSUE_043 / ISSUE_056)

`codes.services.operational_controller` is the deterministic oversight layer
for providers, databases, queues, workers, caches, and data-quality probes.
It is observation-only by default. A deployment must explicitly register an
allowlisted `RecoveryAction` and disable observation-only mode before any
remediation can run.

The controller exposes one active platform mode from `NORMAL`, `WATCH`,
`DEGRADED`, `CONSTRAINED`, `READ_ONLY`, `MAINTENANCE`, `RECOVERING`, and
`EMERGENCY` (with `UNAVAILABLE` retained as a terminal health state). Probe
failures become `UNAVAILABLE`; they never disappear as a healthy result.
Recovery has bounded attempts, cooldowns, mandatory verification, and an audit
event for every attempted action. Essential work is allowed during degraded or
constrained modes while optional work is shed. Read-only mode permits only
essential work; maintenance and emergency modes pause dispatch.

Mode transitions are deterministic and auditable. Automatic changes respect a
minimum dwell time, and recovery out of a safety mode requires consecutive
confirmations. Operators can request a safety mode through `set_mode`; this is
still server-side and audit logged. The controller does not infer permissions,
restart processes, or mutate user or financial data.

The internal performance response exposes `mode`, `message`, component health,
and the last accepted transition. User-facing surfaces should use the message
as an operational explanation and should not independently reinterpret the
mode policy.

Rollout starts with observation-only telemetry. Low-risk actions such as cache
fallback or request deduplication may be enabled independently after their
verification probes are proven. Rollback is disabling remediation or reverting
the controller module; no financial or historical data is overwritten.
