# PostgreSQL least-privilege role operations

## Purpose and ownership

This runbook is the deployment and incident contract for ISSUE_082. Platform/SRE
owns canonical role provisioning, environment LOGIN principals, database secret
distribution, rotation, emergency revocation, and permission monitoring. The
release process owns schema migrations and object ownership. Application teams
must not grant database privileges from request, worker, or startup paths.

No credential, password, connection URL, tenant row, or environment-specific
login name may be logged or committed. Production credentials belong in the
deployment secret manager and are restart-required.

## Canonical workload matrix

| Canonical NOLOGIN role | Credential consumers | Users database | Market database | Analytics database |
|---|---|---|---|---|
| `cenvarn_app` | Web/API runtime | Tenant-table DML under forced RLS; no waitlist access | Current application DML | Product telemetry and snapshot DML |
| `cenvarn_service` | Explicit Stripe, waitlist, reconciliation, and erasure paths | Service-policy DML; no `BYPASSRLS` | No connection | No connection |
| `cenvarn_migration` | Release process only | Schema/object owner | Schema/object owner | Schema/object owner |
| `cenvarn_market_worker` | SEC, Canada, analysis, and market workers | No connection | Current market DML | No connection |
| `cenvarn_readonly` | Controlled operational diagnostics | Migration metadata only | Public/shared market reads | Migration metadata only |

All canonical roles are `NOLOGIN`, `NOSUPERUSER`, `NOCREATEDB`,
`NOCREATEROLE`, `NOREPLICATION`, and `NOBYPASSRLS`. Environment-specific
LOGIN principals must be members of exactly one canonical role. Normal and
worker processes fail startup when membership, flags, schema authority, object
ownership, URL separation, or secret exposure violates this matrix.

Read-only access deliberately excludes users and analytics rows until approved
masked/minimized views exist. Operators must not grant direct tenant-table reads
as a shortcut.

## Initial provisioning and rollout

Classify this as a one-way-door security rollout. Take a current backup, confirm
restore readiness, identify the rollout owner, and keep application/worker
processes stopped while changing existing ownership.

1. Connect as the cluster/database administrator and apply
   `deploy/postgresql/001_canonical_roles.sql` once per cluster.
2. Create environment-specific blue and green LOGIN principals without putting
   passwords in a SQL file. Use an interactive password command or the managed
   provider's secret interface, then grant exactly one canonical membership.
   Example names are `production_cenvarn_app_blue` and
   `production_cenvarn_app_green`; names are illustrative, not required.
3. While connected as the database owner, apply the matching database access
   script to the users, market, and separate analytics databases:
   `002_users_database_access.sql`, `003_market_database_access.sql`, and
   `004_analytics_database_access.sql`.
4. Inject runtime and migration URLs from the secret manager. Do not make
   `DATABASE_MIGRATION_*` values available to web or worker processes. Do not
   make users or service URLs available to market workers.
5. Run `./scripts/release-migrate.sh`. Versioned migrations assign object grants,
   default privileges, and users-service RLS policies after every schema change.
6. Run production configuration validation and start one workload at a time.
   Startup catalog checks must pass before traffic or jobs are enabled.
7. Verify tenant isolation, service workflows, worker ingestion, analytics
   writes, permission-denied metrics, and database authentication errors. Keep
   the prior deployment available until the new identities are healthy.

The administrator should use `psql -v ON_ERROR_STOP=1 -f <script>` with the
appropriate connection URL supplied by the secret manager. Never pass a
password as a command-line argument or enable shell tracing.

## Blue/green credential rotation without downtime

Each workload keeps two environment-specific LOGIN principals with identical
single-role membership. Only one is active in deployment secrets.

1. Confirm the inactive principal has exactly one canonical membership and all
   dangerous role flags are false.
2. Set a new random password through the managed secret interface or interactive
   `psql` password command.
3. Test a direct connection and the bounded startup role check with the inactive
   principal.
4. Update the deployment secret to the inactive principal and perform a rolling
   restart with normal health/readiness gates. Existing pooled connections using
   the old principal remain valid while new instances establish new pools.
5. Observe authentication failures, permission denials, startup rejections,
   connection saturation, and application error rate through at least one full
   workload cycle.
6. Drain old instances and terminate any remaining old-principal backends.
7. Set the old principal `NOLOGIN`, replace its password, and record the rotation
   time, actor, affected workload, and verification result without secret data.
8. Retain the disabled principal as the next rotation target. Do not grant it a
   second canonical membership.

Rollback before step 6 means restoring the old deployment secret and rolling
instances back. After old connections are terminated, repair forward with the
new credential unless incident command explicitly authorizes re-enabling the
old principal.

## Emergency revocation and containment

For suspected credential exposure:

1. Declare the security incident and identify the exact environment LOGIN
   principal; do not disable a shared canonical role unless all member workloads
   must stop.
2. Execute `ALTER ROLE <login> NOLOGIN` through the protected administrator
   channel, rotate/remove its secret, and terminate its PostgreSQL backends.
3. Confirm no unauthorized canonical membership, object ownership, schema
   creation, role flag, or cross-database CONNECT grant was added.
4. Activate the prepared inactive principal through the normal rolling process.
5. Review database authentication, permission-denial, DDL, role-membership, and
   sensitive service-operation audit records for the exposure window.
6. Reapply the provisioning and versioned permission scripts, rerun startup and
   isolation tests, and document containment, affected data, recovery, and
   follow-up owners in the incident record.

Do not recover by granting superuser, `BYPASSRLS`, schema ownership, a migration
secret to runtime, or users credentials to a market worker.

## Monitoring and periodic review

Platform/SRE owns alerts for repeated authentication failures, role-verification
startup failures, permission-denied spikes, unexpected DDL, canonical membership
changes, long-lived disabled-principal sessions, pool saturation, and migration
failure. Quarterly and after every schema change, compare catalog state with the
matrix, enumerate members of every canonical role, confirm `PUBLIC` revocations
and default privileges, and test one blue/green rotation in staging.

## Recovery and compatibility

Provisioning and permission scripts are idempotent and do not rewrite business
rows. If any check fails, keep the affected workload offline and repair grants or
ownership forward. Do not disable forced RLS or restore shared/superuser runtime
credentials. Application rollback is safe only while the stricter PostgreSQL
boundary remains in place.
