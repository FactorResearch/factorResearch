# Request and correlation context (ISSUE_049)

`codes.core.request_context` owns request, correlation, operation, and parent
operation IDs in a `contextvars` context. Flask creates a sanitized root
context before every request, returns `X-Request-ID`, `X-Correlation-ID`, and
`X-Operation-ID`, and restores the previous context during teardown even when
the request fails.

## Propagation

The adaptive job queue captures the immutable context at submission and binds
it only while the worker executes the job. The durable analysis queue serializes
the request, correlation, operation, and parent-operation IDs with the job and
rebinds them at dispatch. Retries retain the same values. Threads that are not
explicitly submitted through a boundary do not inherit context, preventing
cross-request leakage.

Audit events automatically read the active context and include operation
lineage. `ContextFilter` enriches log records with the same safe identifiers;
application code must continue to log outcomes and identifiers only, never
request payloads, credentials, or portfolio contents.

Client-supplied IDs are accepted only when they match the bounded opaque-ID
character policy; otherwise new server-generated IDs are used. Correlation IDs
are diagnostic metadata, not authorization data. IDs are not persisted as
secrets and are safe to expose in response headers.
