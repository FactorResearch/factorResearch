# Purpose

Define mandatory rules for designing, implementing, versioning, documenting, testing, and operating internal and public APIs.

# Core principles

- APIs are long-lived contracts, not implementation details.
- Breaking changes require explicit versioning, migration, and deprecation plans.
- Request and response schemas must be typed, validated, documented, and contract-tested.
- API behavior must remain consistent across success, partial success, degraded operation, and failure.

# Mandatory API contract

Every endpoint must define:

- Purpose and owning service.
- Authentication and authorization requirements.
- Request parameters, body schema, validation, units, and defaults.
- Response schema, field meanings, nullability, units, ordering, and freshness.
- Error codes and stable machine-readable error identifiers.
- Pagination, filtering, sorting, and maximum page size.
- Idempotency behavior.
- Rate limits, timeout expectations, retry safety, and cache behavior.
- Data provenance and whether each result is authoritative, calculated, estimated, stale, or unavailable.

# Naming and structure

- Use nouns for resources and predictable HTTP methods.
- Avoid action-heavy endpoint names unless modeling a true command.
- Use consistent pluralization and casing.
- Do not expose database table structure directly.
- Use a single project-wide error envelope.

# Versioning and compatibility

- Prefer additive, backward-compatible changes.
- Never silently change field meaning, units, or nullability.
- Breaking changes require a new version or migration mechanism.
- Deprecations require notice, telemetry, replacement guidance, and a removal date.

# Reliability

- Every external call must have explicit timeouts.
- Retries are permitted only for retry-safe operations and must use bounded exponential backoff with jitter.
- Mutating requests must support idempotency where duplicate submission is possible.
- Partial section failures must not discard successful independent sections.

# Documentation and testing

- Maintain OpenAPI or equivalent machine-readable contracts.
- Add unit, integration, contract, authorization, failure-path, and regression tests.
- CI must detect incompatible schema changes.
- Examples must show successful, validation-error, authorization-error, degraded, and partial-failure responses.

# AI implementation requirements

Before modifying an API, the AI must load this page, inspect existing contracts, identify compatibility risks, write the contract and failure behavior first, and then implement the smallest safe change.