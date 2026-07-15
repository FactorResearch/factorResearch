# Service Degradation and Emergency Control

1. Correlate request errors/latency with database, Redis, queue, provider, worker, and release telemetry.
2. Declare incident severity and freeze deployments. Treat missing telemetry as loss of control, not success.
3. Roll back the current release when degradation began after deployment and rollback criteria are met.
4. Disable cold analysis or writes at the edge when dependencies cannot preserve correctness; serve an explicit maintenance state.
5. Keep health, status, and operator access available. Never implement read-only mode by bypassing authorization.
6. Restore traffic in stages after two healthy synthetic intervals; monitor SLO burn for 30 minutes.
