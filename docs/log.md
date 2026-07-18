# Purpose
Ensure production behavior can be understood, measured, diagnosed, and improved without reproducing every failure locally.
# Structured logging
- Use structured, machine-readable logs.
- Include timestamp, severity, service, environment, operation, correlation ID, and relevant non-sensitive identifiers.
- Log outcomes and decisions, not noisy line-by-line execution.
- Never log secrets or unnecessary personal data.
# Metrics
Track customer and system outcomes, including:
- Request volume, success, failure, and latency.
- Provider latency, error rate, rate-limit events, and fallback use.
- Worker throughput, queue age, retries, and dead-letter counts.
- Cache hits, misses, staleness, and invalidations.
- Database latency, pool saturation, and slow queries.
- Partial section failures and degraded responses.
# Tracing
Use correlation IDs across API requests, jobs, providers, databases, and caches. Distributed operations must be traceable end to end.
# Alerts
- Alerts must be actionable, owned, severity-classified, and linked to runbooks.
- Alert on customer impact and exhausted error budgets, not every transient error.
- Deduplicate related alerts and avoid alert fatigue.
# Dashboards
Dashboards must show customer experience, dependency health, data freshness, background processing, and deployment impact.
# AI implementation requirements
Every production feature must define logs, metrics, traces, alerts, dashboards, and redaction requirements before implementation is complete.
