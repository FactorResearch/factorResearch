# Idempotent commands and writes (ISSUE_064)

`codes.services.idempotency.IdempotencyService` is the shared command boundary
for retried mutations. A command is identified by authenticated `user_id`,
`Idempotency-Key`, operation name, and a canonical request hash.

The PostgreSQL `idempotency_records` table claims the key atomically before the
handler runs. Completed and failed outcomes are stored and replayed; a second
request with the same key but a different payload is rejected. A concurrent
processing claim returns an in-progress error rather than running the side
effect twice. Ambiguous handler failures are recorded as terminal failures so
clients do not unknowingly duplicate a payment or write.

The additive migration runs in the users database and records expire after 24
hours. Retention is longer than normal retry windows to cover client
reconnection and incident investigation. Rollout is additive: deploy the
table, then enable keyed commands; rollback stops accepting new keys while
retaining records for replay analysis.

Portfolio create/add/remove mutations, Stripe checkout session creation, and
job submission support keys. Stripe also receives the key through its native
idempotency mechanism. Unkeyed legacy calls retain existing behavior for
backward compatibility, while new mutating API commands must require a key at
their request boundary.
