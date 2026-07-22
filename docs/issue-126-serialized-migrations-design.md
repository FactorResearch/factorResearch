# ISSUE_126 — Serialized database initialization and migrations

## Outcome and verified gap

Cenvarn must never let two release processes mutate the same PostgreSQL schema
concurrently, and normal web or worker processes must not need schema-owner
credentials. Today `apply_migrations()` reads and writes `schema_migrations`
without a database-wide lease, while `init_db()` and `init_user_db()` execute
DDL from runtime-accessible code. The process-local `_market_initialized` and
`_users_initialized` flags are also unsynchronized and become true without a
database readiness contract.

The required outcome is a bounded, transactional release phase that serializes
each database and migration scope, plus fail-closed runtime readiness checks
that are safe under threads and multiple processes.

## Customer, success criteria, and non-goals

The internal customers are release operators and every web or worker process
that depends on PostgreSQL. A successful release applies a scope at most once,
records each migration checksum atomically with its SQL, and produces a clear
timeout or readiness error instead of serving against partial schema state.

This issue does not provision PostgreSQL roles, implement row-level security,
rewrite the repository layer, convert unrelated analytics schema code into a
new migration framework, or certify the final production release candidate.
Role grants remain owned by ISSUE_082 and full runtime evidence by ISSUE_125.
It does define and enforce the application-side credential and process
boundaries those issues require.

## Decision classification

This is a one-way-door operational boundary because it changes who may mutate
production schema and makes incomplete deployments fail closed. The SQL schema
changes remain additive and transactional; rollback restores the prior release
code, but operators must retain the dedicated migration phase once normal roles
no longer own schema objects.

## Existing contracts and smallest viable design

The implementation reuses Psycopg transactions, the existing bounded
`ConnectionPool`, versioned SQL files, the release `Procfile` phase, and the
existing `codes.data.migrate` command. PostgreSQL advisory transaction locks
provide the cross-process primitive; no dependency is added.

The smallest safe change is:

1. Acquire a PostgreSQL transaction-level advisory lock before reading or
   changing migration state. The current database provides the database part
   of the identity and a stable signed 64-bit hash provides the scope part.
2. Poll `pg_try_advisory_xact_lock` until a monotonic deadline. This keeps the
   wait bounded and produces a domain-specific timeout without relying on a
   server-wide setting.
3. Execute base schema SQL, ordered migration SQL, and checksum inserts inside
   the caller-owned transaction. Any exception rolls the complete scope back,
   including its advisory lock.
4. Give the release process separate migration URLs. Production migration
   execution fails closed if those URLs are absent or equal to runtime URLs.
5. Replace lazy runtime DDL with read-only readiness verification. A required
   table, migration record, or checksum mismatch prevents normal work.
6. Protect process-local readiness caches with locks. PostgreSQL remains the
   authority; a flag becomes true only after a successful database check.

## Interfaces and state transitions

`apply_migrations(connection, scope, bootstrap_sql=..., lock_timeout_seconds=...)`
is the release-only migration boundary. It accepts an open connection whose
transaction is committed or rolled back by the caller. The state transition is:

`unlocked -> advisory lock held -> bootstrap verified/applied -> migrations
verified/applied -> transaction committed -> lock released`.

`verify_migrations(connection, scope, required_tables=...)` is read-only. It
requires `schema_migrations`, every declared base table, every repository
migration record, and matching checksums. It returns normally only for a ready
scope and otherwise raises `DatabaseNotReadyError`.

`db.verify_runtime_databases()` checks market and users readiness without DDL.
Repository lazy guards call the corresponding verification once per process,
using one lock per scope for thread safety.

## Transaction, concurrency, and interruption behavior

The advisory lock is transaction-scoped, so PostgreSQL releases it on commit,
rollback, connection loss, or process termination. Bootstrap DDL, one migration
file, and its checksum record share the same outer transaction. A process killed
after DDL but before completion therefore leaves neither partial DDL nor a false
checksum record when the statements are transaction-safe.

Migration files that require transaction-prohibited operations such as
`CREATE INDEX CONCURRENTLY` are intentionally unsupported by this runner and
must use a separately designed release step. The current migrations contain no
such operation.

## Failure modes and recovery

- Lock contention past the configured deadline raises
  `MigrationLockTimeoutError`; no migration state is read or changed.
- A missing database or insufficient privilege propagates a sanitized
  operational failure and rolls back the transaction.
- A missing tracker table, required table, or expected migration causes runtime
  readiness to fail before data access or traffic startup.
- A checksum mismatch raises `MigrationChecksumError` in both release and
  runtime paths. Operators restore the original migration file or add a new
  forward migration; they never edit the recorded checksum.
- An interrupted release can be rerun. PostgreSQL rollback and the advisory
  lock make recovery idempotent.

Retries are operator-controlled by rerunning the bounded release phase. The
application does not loop indefinitely or serve a degraded partial schema.

## Security and privacy

Migration URLs are secrets and must only be injected into the release process.
They are never logged. Production validation requires distinct migration and
runtime URLs for each database. Normal runtime readiness uses catalog and
tracker reads only and does not require schema ownership. The change processes
no customer payload and adds no personal-data logging.

ISSUE_082 remains responsible for provisioning and granting `cenvarn_migration`
and the least-privilege runtime roles. ISSUE_080 remains responsible for RLS.

## Observability and ownership

The data/platform owner owns the migration command and recovery runbook; the
release owner invokes it before web and worker rollout. Stable structured log
events report scope, outcome, elapsed time, and migration count without DSNs or
SQL payloads. Lock timeout, checksum drift, readiness failure, and migration
failure are distinct error categories suitable for release alerts.

The runbook is this document until an operations runbook issue supplies a
central location. The design should be reviewed whenever migration tooling or
deployment topology changes; initial review date is 2026-07-22.

## Performance and cost

The release path is infrequent and serial by design. Runtime readiness performs
bounded catalog and migration-table reads once per database per process. No new
service, package, retained background task, or recurring infrastructure cost is
introduced.

## Deployment and rollback

Deploy the release command first with dedicated migration credentials, run it
to completion, then start least-privilege web and worker processes with only
runtime credentials. A failed release phase blocks rollout. Post-deployment
verification starts at least two normal processes and confirms both pass the
read-only readiness check.

Rollback stops the new application version and deploys the prior compatible
version. Additive schema objects remain in place. Do not delete
`schema_migrations` or rewrite checksum rows. If role separation has already
removed runtime DDL privileges, keep the dedicated migration phase even while
rolling application code back.

## Test strategy

Focused deterministic tests must prove stable lock keys, successful and timed
out advisory lock acquisition, one transaction-owned bootstrap/migration flow,
checksum mismatch detection, missing and partial schema detection, rollback
propagation, repeated migration idempotency, distinct production migration
credentials, and thread-safe runtime initialization.

PostgreSQL integration evidence must additionally run two migration processes
against an empty database, interrupt a transaction after DDL, start multiple
web/worker processes against partial state, and exercise insufficient privilege
and unavailable database failures. If the local environment cannot provide the
required PostgreSQL roles/process harness, those exact commands and the resume
condition will be recorded on the issue rather than represented by mocks.

## Open risks

The repository still contains other modules with legacy lazy `CREATE TABLE`
behavior. This issue removes normal startup mutation from the market and users
database boundary named in the specification; each additional owning database
must adopt the same release/readiness split before receiving a least-privilege
runtime role. Final multi-service certification remains part of ISSUE_125.
