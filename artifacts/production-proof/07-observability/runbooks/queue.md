# Queue Backlog or Dead Letters

1. Record queued, processing, oldest-age, and dead-letter counts plus active worker versions.
2. Stop producers if age is growing and capacity cannot catch up; do not purge evidence.
3. Inspect redacted failure categories and correlate request/job IDs to provider and persistence telemetry.
4. Fix the dependency or deploy a compatible worker before replay.
5. Replay a bounded sample from dead letter; verify idempotency and one persisted result per job.
6. Drain gradually. Close only after queue age returns to target and no new dead letters appear for 15 minutes.
