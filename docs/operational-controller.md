# Operational health controller (ISSUE_043)

`codes.services.operational_controller` is the deterministic oversight layer
for providers, databases, queues, workers, caches, and data-quality probes.
It is observation-only by default. A deployment must explicitly register an
allowlisted `RecoveryAction` and disable observation-only mode before any
remediation can run.

The controller exposes `WATCH`, `DEGRADED`, `CONSTRAINED`, `RECOVERING`, and
`UNAVAILABLE`. Probe failures become `UNAVAILABLE`; they never disappear as a
healthy result. Recovery has bounded attempts, cooldowns, mandatory
verification, and an audit event for every attempted action. Essential work is
allowed during constrained/degraded states while optional work is shed.

Rollout starts with observation-only telemetry. Low-risk actions such as cache
fallback or request deduplication may be enabled independently after their
verification probes are proven. Rollback is disabling remediation or reverting
the controller module; no financial or historical data is overwritten.
