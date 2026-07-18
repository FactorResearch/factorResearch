# Purpose
Make external data providers replaceable, observable, normalized, licensed correctly, and isolated from domain logic.
# Provider abstraction
- Application and domain layers must depend on project-owned interfaces.
- Provider-specific payloads must not escape adapters.
- Normalize field names, units, dates, currencies, nullability, and error behavior.
# Provider contract
Each provider must document:
- Supported datasets and markets.
- Licensing and redistribution constraints.
- Rate limits and cost model.
- Freshness and expected delays.
- Authentication and secret requirements.
- Timeout, retry, fallback, and circuit-breaker behavior.
- Known field inconsistencies and historical limitations.
# Source selection
Define primary and fallback order per data type. Conflicts between providers require deterministic resolution and provenance retention.
# Data quality
Validate schemas, units, dates, ranges, duplicate records, corporate actions, and freshness before accepting data.
# Replacement strategy
Critical providers require an exit path, adapter tests, and minimal provider-specific coupling.
# Observability
Measure latency, availability, rate-limit use, cost, stale responses, rejected records, and fallback frequency.
# AI implementation requirements
The AI must inspect existing adapters and licensing constraints before introducing or changing provider behavior.
