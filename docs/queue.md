# Background job queue (ISSUE_047)

The queue boundary is `codes.services.adaptive_loading.AdaptiveJobStore` for
interactive UI jobs and `codes.services.analysis_jobs` for durable analysis
refresh work. Web callbacks submit work and return a job ID; polling reads a
tenant-scoped status snapshot and never executes the long-running operation in
the request.

## Job contract

Each adaptive job has a stable ID derived from operation, owner, and dedupe
key; a priority, timeout, retry bound, progress state, heartbeat timestamp,
and terminal history. Duplicate active or successful submissions reuse the
existing job. Interactive jobs are selected before maintenance jobs. A
cooperative timeout or cancellation sets the job's cancellation signal, and
job code must check it at safe checkpoints.

Transient failures retry only within the configured maximum. Permission,
validation, entitlement, and not-found failures do not retry. Exhausted or
timed-out work is recorded as a dead letter and cannot prevent later healthy
jobs from running. Owner checks prevent status and result leakage across users.

The analysis worker uses Redis queues with separate interactive and maintenance
lanes, processing recovery, bounded retry metadata, terminal dead-letter
records, and a worker heartbeat with a short expiry. Redis is required for
production analysis workers; local execution is a development fallback only.

## Operations and rollout

Monitor queue depth, processing count, oldest heartbeat age, retry counts,
terminal failures, dead letters, and worker heartbeat freshness. Deploy the
queue worker separately from web processes, verify health and a successful
test job, and roll back by stopping the worker role and returning traffic to
the previous request path. Existing job IDs and status contracts remain
backward-compatible.
