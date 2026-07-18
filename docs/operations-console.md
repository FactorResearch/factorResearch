# Internal operations console (ISSUE_058)

The internal console is a server-side administrative boundary. It is
available only to authenticated user IDs listed in
`OPERATIONS_ADMIN_USER_IDS`; an absent or invalid identity receives a not-found
response so the endpoint does not disclose its existence.

The first release is intentionally limited to reversible, pre-approved
actions: feature kill-switch changes, validated configuration reload/rollback,
provider circuit reset, and process-local component-cache invalidation. Every
action requires exact confirmation (`confirm:<action>`), validates typed
parameters, and appends a redacted audit-journal event. Database mutations,
user-data operations, queue/job deletion or release, shell access, and process
restart are excluded.

Configuration and feature actions delegate to their existing services, so their
validation, persistence, cache invalidation, and audit behavior remain
authoritative. Provider reset and local cache clearing have no network or
database side effects and can be rolled back by re-observing the component.
