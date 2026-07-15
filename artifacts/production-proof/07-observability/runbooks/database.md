# Database Failure

1. Confirm the affected pool in `/_internal/performance`; compare application, analytics, and snapshot pools.
2. Check provider status, connection count, saturation, locks, storage, and recent migrations without printing connection strings.
3. Stop nonessential writers and background refreshes. Preserve reads when the database is healthy enough.
4. For pool exhaustion, identify leaked/long transactions before increasing limits. Cancel only verified disposable work.
5. For outage or read-only state, enable maintenance/read-only controls at the edge and pause workers.
6. Restore service or fail over using the approved database procedure; verify schema version and recent authoritative writes.
7. Resume one worker, then web traffic. Watch errors, latency, pool utilization, and queue age for 15 minutes.
8. Escalate to incident command for data loss, cross-user exposure, or an RPO breach.
