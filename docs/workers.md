# Purpose

Define safe, observable, restartable, and idempotent background processing for SEC ingestion, refresh jobs, scoring, analytics, exports, and future pipelines.

# Mandatory job contract

Every job must define:

- Purpose and owner.
- Input schema and version.
- Idempotency key.
- Retry policy.
- Timeout.
- Concurrency and locking rules.
- Progress and completion states.
- Cancellation behavior.
- Dead-letter or terminal-failure behavior.
- Reprocessing procedure.

# Reliability

- Jobs must tolerate worker restart.
- Retried jobs must not duplicate durable effects.
- Use bounded exponential backoff with jitter.
- Poison jobs must not block the queue.
- Long jobs should checkpoint safe progress.
- Partial success must be recorded explicitly.

# Data integrity

- Use transactions for atomic write groups.
- Prevent concurrent writers from corrupting the same logical record.
- Record source, run ID, timestamps, and status.

# Observability

Track queue depth, oldest job age, processing latency, throughput, retries, failures, dead letters, and worker health.

# AI implementation requirements

The AI must design failure recovery, idempotency, locking, and monitoring before implementing a worker.