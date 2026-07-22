# ISSUE_116 — PostgreSQL portfolio authority

## Decision

PostgreSQL is the production source of truth for portfolios, holdings,
portfolio mutation history, tombstones, simulation results, and legacy-import
evidence. Local files are accepted only by the explicit release importer and
as a non-production compatibility adapter. Production startup rejects an
attempt to select cache authority.

## Data and tenant boundary

Migration `003_issue_116_portfolio_authority_users.sql` creates six normalized
tables. Every tenant-owned row stores `owner_id`. Child tables use composite
foreign keys `(portfolio_id, owner_id)` so a row cannot be attached to another
tenant's portfolio even if its UUID is known.

Every table has row-level security enabled and forced. Policies require
`owner_id = NULLIF(current_setting('app.current_user_id', true), '')` for reads
and writes after ISSUE_080's canonical policy migration. The shared users
connection boundary validates a non-empty authenticated user ID and sets this
value transaction-locally before every query. Missing context fails before SQL
execution. PUBLIC receives no table privileges. The release command derives
the normal users runtime role from `DATABASE_USERS_URL` and grants only schema
usage plus tenant-table DML; schema ownership and DDL remain with the migration
role. Privileged Stripe, waitlist, and erasure operations use the distinct
`DATABASE_USERS_SERVICE_URL` credential.

## Mutations and simulations

Portfolio writes lock the target row, compare the caller's expected version,
advance the version, replace the normalized holding set, and append mutation
records in one database transaction. A stale writer fails without committing
partial state. Soft deletion writes a separately discoverable tombstone;
restoration requires the tombstone version.

Simulation rows are owner scoped, tied to a portfolio version and model
version, keyed by a checksum of the exact holdings input, and expire after 24
hours. A holding mutation changes the portfolio version, so an old simulation
cannot be reused. The legacy `port_sim` compatibility cache is encrypted.

## Legacy rollout and rollback

1. Run the serialized users migration release phase.
2. Provide an approved list of authenticated owner IDs through
   `LEGACY_PORTFOLIO_USER_IDS_FILE`, or run
   `python -m codes.data.migrate_portfolios --user-file FILE` explicitly.
3. The importer discovers indexed, soft-deleted, and orphaned hashed files,
   records a checksum and status for every source, writes PostgreSQL rows, and
   reads them back before clearing any child file or index.
4. A retry with the same checksum is a no-op. Conflicting PostgreSQL state
   fails closed. A partial attempt deletes rows created by that attempt while
   retaining the encrypted source files and a failed import record.
5. Use `--keep-files` when retention approval is pending. Production cutover is
   incomplete until the approved purge runs and no user holdings remain in
   local files.

Application rollback may disable the PostgreSQL adapter only outside
production. Production rollback restores the previous database backup or
application version while retaining the additive schema and import evidence;
it never silently returns local files to authority.

## Export, erasure, and backup evidence

Account export discovers active and deleted portfolios, normalized holdings,
mutation history, tombstones, simulations (including expired/deleted rows),
completed or failed imports, and remaining legacy projections. Account
erasure deletes every one of those PostgreSQL categories and then discovers
and deletes hashed and indexed legacy files. File indexes are cleared only
after child files.

`scripts/backup_db.sh` streams the complete users database through AES-256-CBC
encryption and refuses an unencrypted backup. `scripts/restore_test.sh`
decrypts only in a pipeline into a scratch database and now verifies all six
portfolio-authority tables survived the restore. ISSUE_083 still owns the
production retention schedule, key custody, and recurring restore operation.

## Verification contract

- Fast tests inspect normalized schema/RLS policy coverage, encrypted
  simulation projections, production fail-closed configuration, adapter
  routing, and orphaned-file discovery.
- Disposable PostgreSQL tests use a non-owner, least-privilege runtime role to
  prove cross-user reads are empty, stale writes fail, separate connections see
  shared state, simulations expire/invalidate, legacy import is idempotent,
  tombstones export correctly, and erasure removes every category.
- ISSUE_126 PostgreSQL migration tests run alongside these tests to prove the
  new schema remains serialized, atomic, and recoverable after interruption.
