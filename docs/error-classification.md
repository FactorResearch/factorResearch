# Central error classification (ISSUE_057)

`codes.core.errors` is the authoritative registry for failure semantics across
services, workers, API adapters, and UI delivery. It translates exceptions into
a stable code, category, severity, retry decision, recovery action, and safe
user copy. Exception messages and tracebacks are diagnostic-only and must never
be used as user-facing text.

## Recovery rules

- Validation, authentication, authorization, not-found, and cancellation
  failures do not retry.
- Dependency and timeout failures are temporary and may retry within the
  caller's bounded retry policy.
- Unknown failures are classified as `internal_error`, are not automatically
  retried by this registry, and are recorded with correlation context by the
  delivery boundary.
- Optional section failures use `PartialResponse`, preserving successful data
  and exposing only structured error payloads for failed sections.

Existing API v1 error payloads intentionally remain backward-compatible with
their three-field contract. The central category, severity, and recovery
metadata remain available to internal consumers and future versioned contracts.

## Observability and rollout

Unhandled request failures emit an `error_classified` audit event containing the
stable code and category, not the raw exception. Worker snapshots store the
stable code so retries and dead-letter inspection use the same vocabulary.
There is no database migration or feature flag: the change is additive and can
be rolled back by reverting the module integrations without changing persisted
financial data.
