# Redis Failure

1. Confirm Redis reachability and distinguish queue, cache, rate-limit, and lock impact.
2. Do not silently substitute per-process rate limiting in production; reduce public traffic if enforcement is inconsistent.
3. Pause job producers when the durable queue is unavailable. Preserve acknowledged in-flight records for recovery.
4. Restore or fail over Redis, then run in-flight recovery before accepting new jobs.
5. Verify queue depth, oldest age, dead letters, duplicate suppression, and rate-limit behavior.
6. Resume producers gradually and monitor for duplicate work for 15 minutes.
