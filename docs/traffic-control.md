# Intelligent traffic control (ISSUE_052)

`codes.app_modules.rate_limit.check_rate_limit` supports weighted request
costs and essential/optional priority. Expensive operations consume more
budget; optional work is denied once the configurable
`TRAFFIC_OPTIONAL_RESERVE_RATIO` is reached, preserving capacity for essential
requests. Redis counters use atomic weighted increments and TTLs when
available; local development falls back to a process-local weighted window.

Rejected decisions return `RateLimited.retry_after` for UI/API handling and
write a redacted audit event. Existing provider-specific windows in
`codes.data.api_fetcher` remain the authoritative provider-quota protection;
this layer protects tenant/action traffic before provider work is submitted.
