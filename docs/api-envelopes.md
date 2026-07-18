# API envelopes and pagination (ISSUE_067)

All `/api/v1` endpoints use the shared `data`/`meta`, collection, and error
envelopes from `codes.api.contracts`. `meta.request_id` is the stable
correlation identifier for both successful and failed requests. Error codes and
retryability come from the central ISSUE_057 registry; optional `details` are
safe, bounded fields only and never contain exception text or secrets.

Collection responses are bounded by `page_size` (1–100). Existing page-based
pagination remains supported for v1 compatibility. Cursor helpers encode only a
non-negative offset in a URL-safe opaque token; cursor requests may return
`next_cursor` and `previous_cursor` without exposing database identifiers.

Optional independent failures use `partial: true` and section-level `errors`
while retaining successful `data`. Consumers must treat missing sections as
unavailable, not as numeric zero. Filtering and sorting remain owned by each
resource service and must be allow-listed before being added to a route.

There is no migration or new dependency. Rollback is a code revert; the
existing v1 page envelope remains valid during rollout.
