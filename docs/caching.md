# Purpose
Define caching as a controlled performance layer without allowing it to become an untracked source of truth.
# Core rules
- The database or authoritative provider remains the source of truth.
- Cache keys must be versioned, namespaced, deterministic, and tenant-safe.
- User-specific data must never leak across users.
- Every cached value requires an owner, TTL, invalidation strategy, and freshness policy.
# Required design decisions
- What is cached and why.
- Cache key format.
- TTL and stale tolerance.
- Invalidation triggers.
- Stale-while-revalidate behavior.
- Negative caching behavior.
- Stampede protection.
- Fallback when cache is unavailable.
- Serialization and schema versioning.
# Prohibited behavior
- Using cache as the only durable copy.
- Infinite TTL without explicit justification.
- Caching authorization decisions longer than their safe lifetime.
- Shared keys that omit user, model version, date, currency, or other required dimensions.
# Observability
Track hit rate, miss rate, latency, evictions, staleness, invalidation failures, and stampede events.
# AI implementation requirements
Before adding caching, the AI must prove the performance need, identify correctness risks, and document invalidation and isolation.
