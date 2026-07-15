# Market-Data Provider Failure

1. Identify the open circuit and provider error/latency trend; verify whether failure is ticker-specific or global.
2. Serve labeled cached snapshots within their approved freshness window. Never present stale data as live.
3. Stop retries that worsen rate limiting; honor `Retry-After` and the circuit breaker.
4. Disable cold analysis if required inputs cannot be obtained accurately.
5. Contact the provider and record incident/ticket IDs. Do not expose credentials in evidence.
6. Recover with a small ticker sample, then gradually restore traffic while checking data completeness.
