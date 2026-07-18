# Purpose
Define mandatory database engineering standards for Factor Research and all future services, workers, APIs, analytics systems, and AI-generated code.
The objective is to make database design predictable, safe, traceable, scalable, and understandable years after implementation. These rules apply to PostgreSQL schemas, migrations, repositories, workers, background jobs, analytics storage, user data, market data, and any future persistent storage system.
# Mandatory AI prerequisite
Before creating or modifying database-related code, the AI agent must load this page into active context and inspect the existing schema, migrations, repository layer, and nearby data-access patterns.
The agent must not generate tables, migrations, SQL, repository methods, persistence models, indexes, or worker write paths until it understands:
- Which database owns the data.
- Which service or worker owns writes.
- Existing naming and migration conventions.
- Current query patterns.
- Existing constraints and indexes.
- Data retention and deletion rules.
- Whether the data is authoritative, derived, cached, or analytical.
- Whether a targeted change is sufficient instead of a broad schema rewrite.
If required context is unavailable, the agent must stop before implementation rather than invent a new database pattern.
# Core database principles
## Database as source of truth
Persistent business state must have one clearly defined source of truth.
The database stores authoritative state. Python contains domain and application logic. JavaScript and TypeScript consume validated contracts and must not recreate persistence rules or authoritative financial calculations.
Derived values may be stored only when the reason is documented, such as performance, historical snapshot preservation, auditability, or reproducibility.
## Clear database boundaries
Factor Research databases must remain separated by responsibility.
Current target boundaries include:
- `factorresearch_users` — users, authentication-related records, preferences, subscriptions, billing references, entitlements, and account-level settings.
- `factorresearch_market` — securities, SEC data, normalized fundamentals, market data, prices, financial-model inputs, calculated market outputs, provenance, and historical analysis snapshots.
- `factorresearch_jobs` — background jobs, worker scheduling, execution state, retries, leases, failures, and job history.
- `factorresearch_analytics` — product telemetry, clicks, searches, feature usage, experiments, and aggregated behavioral analytics.
Data must not be placed in a database merely because it is convenient for the current feature.
Cross-database coupling must be minimized and explicitly documented. Database-level foreign keys cannot safely enforce relationships across separate databases, so cross-database identifiers require application-level contracts, reconciliation, and monitoring.
## One authoritative writer
Every table must have one clearly identified owning service, worker, or subsystem responsible for authoritative writes.
Multiple writers are prohibited unless explicitly designed and documented with:
- Conflict-resolution rules.
- Transaction boundaries.
- Idempotency behavior.
- Ordering guarantees.
- Concurrency controls.
- Reconciliation strategy.
# Naming standards
## Database objects
Use lowercase `snake_case` for:
- Databases
- Schemas
- Tables
- Columns
- Indexes
- Constraints
- Views
- Materialized views
- Sequences
- Triggers
- Stored procedures
Examples:
```sql
portfolio_holdings
market_cap
latest_filing_date
idx_price_history_ticker_date
uq_portfolio_holdings_portfolio_ticker
fk_portfolio_holdings_portfolio
```
## Primary and foreign keys
Use:
- `id` for a table's primary key when the entity has an internal surrogate identifier.
- `<entity>_id` for foreign keys.
- Stable natural identifiers only when their immutability and uniqueness are guaranteed.
Examples:
```sql
id
portfolio_id
user_id
security_id
analysis_id
```
Avoid inconsistent variants such as:
```plain text
portfolioID
PortfolioId
portfolio_fk
pid
```
## Boolean columns
Boolean columns must use names that read clearly as true or false:
- `is_active`
- `has_errors`
- `can_retry`
- `should_refresh`
Avoid ambiguous names such as `active`, `flag`, or `status_bool`.
## Time columns
Use explicit names such as:
- `created_at`
- `updated_at`
- `deleted_at`
- `refreshed_at`
- `published_at`
- `effective_at`
- `expires_at`
- `as_of_date`
The name must communicate whether the value is an event time, effective business date, ingestion time, or refresh time.
# Table documentation requirements
Every table must have documentation describing:
- Purpose.
- Owning database.
- Owning writer.
- Read consumers.
- Authoritative or derived status.
- Update frequency.
- Expected growth rate.
- Retention policy.
- Deletion policy.
- Primary key.
- Foreign keys.
- Unique constraints.
- Important check constraints.
- Indexes and their query purpose.
- Data lineage.
- Freshness expectations.
- Recovery and rebuild strategy.
Complex columns must also document:
- Units.
- Currency.
- Time zone.
- Nullability meaning.
- Allowed range.
- Source provider.
- Whether values are raw, normalized, calculated, estimated, or display-only.
# Schema design standards
## Explicit constraints
The database must enforce invariants whenever practical.
Use:
- `NOT NULL`
- `UNIQUE`
- `PRIMARY KEY`
- `FOREIGN KEY`
- `CHECK`
- Domain types or approved enums where appropriate
Do not rely exclusively on application code for rules the database can enforce safely.
Examples:
```sql
CHECK (weight_percentage >= 0 AND weight_percentage <= 100)
CHECK (retry_count >= 0)
CHECK (currency_code ~ '^[A-Z]{3}$')
```
## Nullability
Every nullable column must have a documented meaning.
`NULL` must not ambiguously represent several states such as unknown, not applicable, not yet loaded, failed, or intentionally omitted.
Where these states matter, use an explicit status field or a richer model.
## Status values
Do not store unexplained numeric status codes such as `status = 3`.
Use documented textual states or a constrained database type:
```plain text
pending
running
completed
failed
cancelled
```
State transitions must be documented and validated.
## Monetary values
Do not use binary floating-point types for authoritative monetary values.
Use an appropriate exact numeric type and store currency explicitly.
Required considerations:
- Currency code.
- Precision.
- Scale.
- Rounding policy.
- Whether the amount is raw, converted, normalized, or display-only.
- Conversion rate and conversion timestamp when applicable.
## Percentages, ratios, and scores
Every percentage, ratio, rate, and score column must document its representation.
Examples:
- `0.15` representing 15%.
- `15.00` representing 15%.
- Basis points.
- A score from 0 to 100.
Do not allow different services to interpret the same column differently.
## Dates and time zones
Store timestamps in UTC using time-zone-aware database types.
Business dates such as filing dates, trading dates, and `as_of_date` values must use date types when time-of-day is not meaningful.
The system must distinguish:
- Event time.
- Ingestion time.
- Effective time.
- Source publication time.
- Last refresh time.
Do not use server-local time or naive timestamps.
# Historical and financial data rules
## Immutable history
Historical financial records, analyses, model outputs, filings, and point-in-time snapshots must not be silently overwritten.
When a source restates or corrects prior data, preserve enough history to identify:
- Previous value.
- New value.
- Source filing or provider record.
- Effective date.
- Ingestion date.
- Reason or version.
Use versioned records, effective-date ranges, append-only snapshots, or other approved temporal patterns.
## Point-in-time correctness
Backtests and historical analyses must use only information available as of the requested historical date.
The schema must preserve publication, filing, acceptance, or availability dates required to prevent look-ahead bias.
## Data provenance
Every material financial input and calculated output must be traceable.
Required provenance may include:
- Provider.
- SEC accession number.
- Filing form.
- Filing period.
- Source field or XBRL concept.
- Source URL or stable identifier.
- Ingestion job.
- Transformation version.
- Calculation version.
- Refreshed timestamp.
- Data-quality flags.
A user-facing score should be traceable from final output to model input and original source.
## Data-quality state
Financial data must support explicit quality and freshness states where necessary:
- `fresh`
- `stale`
- `estimated`
- `partial`
- `restated`
- `missing`
- `invalid`
- `provider_fallback`
Do not hide data-quality problems by storing a plausible default value.
# Repository and data-access rules
## Repository boundary
Application services, routes, controllers, UI code, and domain models must not contain raw SQL.
Approved flow:
```plain text
Route or worker
→ application service
→ repository interface
→ PostgreSQL repository implementation
→ database
```
Domain calculations must not access the database directly.
## Parameterized queries
All dynamic SQL values must use parameterized queries.
String interpolation, concatenation, and manual escaping for user-controlled or variable values are prohibited.
## Explicit column selection
`SELECT *` is prohibited in production repositories, views consumed as contracts, migrations, and application queries.
Queries must specify required columns explicitly.
## Query return contracts
Repository methods must return named models, schemas, dataclasses, or typed records.
Ambiguous tuples and untyped dictionaries are prohibited at application boundaries.
## Read and write separation
Repository interfaces should clearly distinguish reads from writes.
Method names must communicate intent, for example:
- `get_portfolio_by_id`
- `list_holdings_for_portfolio`
- `insert_analysis_snapshot`
- `update_job_lease`
- `mark_job_failed`
Avoid vague methods such as `save`, `process`, `run_query`, or `get_data` unless the entity and operation are unmistakable.
# Query design standards
## Pagination
Queries over potentially large result sets must use bounded pagination or streaming.
Unbounded reads are prohibited.
The pagination strategy must be appropriate for the access pattern:
- Keyset pagination for large, frequently changing tables.
- Offset pagination only where its limitations are acceptable.
- Stable deterministic ordering for every paginated query.
## N+1 prevention
Every data-access change must evaluate query count.
Code review must reject accidental N+1 query patterns.
Use joins, batch loading, aggregation, prefetching, or dedicated read models where appropriate.
## Query plans
Material or high-frequency queries must be reviewed with `EXPLAIN` or `EXPLAIN ANALYZE` in an environment with representative data.
Review:
- Sequential scans.
- Index usage.
- Estimated versus actual rows.
- Sort operations.
- Join strategy.
- Memory and temporary disk use.
- Locking behavior.
## Complex SQL documentation
Complex queries must include a clear explanation immediately above the repository method or migration block describing:
- Business purpose.
- Join logic.
- Filtering assumptions.
- Ordering guarantees.
- Null handling.
- Performance considerations.
- Why a simpler query is insufficient.
# Index standards
## Indexes follow query patterns
Indexes must be created for documented access patterns, not by guessing.
Every index must have a stated purpose and expected consumer.
## Composite indexes
Composite index column order must reflect filtering, equality predicates, ranges, joins, and sorting requirements.
Do not create redundant indexes whose leading columns are already covered without documented benefit.
## Index cost
Every new index must consider:
- Write amplification.
- Storage cost.
- Vacuum impact.
- Build time.
- Locking.
- Whether it duplicates an existing index.
Unused indexes must be monitored and reviewed before removal.
## Unique indexes
Use unique constraints or indexes for true business uniqueness rather than relying on pre-insert existence checks.
# Transaction standards
## Atomic writes
Multi-step writes that must succeed or fail together must run within one transaction.
The transaction boundary must be owned by the application service or approved unit-of-work layer, not hidden unpredictably across several repository methods.
## Transaction size
Keep transactions short.
Do not perform slow network requests, long computations, or user interactions while holding an open database transaction.
## Isolation and concurrency
Concurrency-sensitive operations must document:
- Required isolation level.
- Locking strategy.
- Lost-update prevention.
- Duplicate-processing prevention.
- Deadlock behavior.
- Retry policy.
Use optimistic or pessimistic concurrency intentionally.
## Idempotency
Worker operations, API writes, webhooks, retries, and migration backfills must be idempotent where repetition is possible.
The database should enforce idempotency using stable keys, unique constraints, leases, or processed-event records where appropriate.
# Migration standards
## Migrations only
All schema changes must use reviewed, version-controlled migrations.
Manual production changes and schema mutation inside application startup code are prohibited.
## Migration requirements
Every migration must document:
- Purpose.
- Forward change.
- Rollback or recovery plan.
- Expected duration.
- Locking risk.
- Data volume.
- Backfill strategy.
- Compatibility window.
- Deployment order.
- Verification query.
## Backward-compatible rollout
Use expand-and-contract migrations for production changes:
1. Add the new schema in a backward-compatible state.
2. Deploy code that can use both old and new representations.
3. Backfill and validate.
4. Switch reads and writes.
5. Observe production behavior.
6. Remove the old schema in a later release.
Do not combine destructive schema removal with the first deployment that stops using it.
## Large table changes
Large-table migrations must avoid long exclusive locks.
Use safe PostgreSQL techniques where applicable, including:
- Concurrent index creation.
- Batched backfills.
- Adding nullable columns before enforcing `NOT NULL`.
- Validating constraints separately.
- Throttled migration workers.
## Migration testing
Migrations must be tested against:
- Empty databases.
- Representative production-like data.
- Upgrade paths from the previous release.
- Rollback or recovery procedures.
- Partial-failure scenarios.
# Deletion and retention standards
## Explicit deletion policy
Every persistent data category must define whether it uses:
- Hard deletion.
- Soft deletion.
- Archival.
- Time-based retention.
- Permanent historical retention.
Soft deletion is not the automatic default. It must be chosen because recovery, auditability, or user experience requires it.
## Personal data
User and personal data must support documented privacy, retention, export, and deletion requirements.
Deleted accounts must not leave undocumented personal data in analytics, logs, backups, derived tables, or caches.
## Cascades
Foreign-key cascade behavior must be explicit and reviewed.
Do not use broad cascading deletes without understanding the complete impact.
# Cache and derived-data standards
## Cache is not authoritative storage
Cached data must be rebuildable or safely disposable.
Cache entries require:
- Stable key format.
- TTL or invalidation strategy.
- Versioning where formats may change.
- Stale-data behavior.
- Stampede protection when necessary.
Do not mix temporary cache rows into authoritative domain tables without a documented design reason.
## Derived tables and materialized views
Derived tables and materialized views must document:
- Source tables.
- Refresh mechanism.
- Refresh frequency.
- Staleness tolerance.
- Rebuild procedure.
- Failure handling.
- Whether consumers may fall back to source tables.
# Worker and job database rules
## Job ownership
Every job type must document:
- Owning worker.
- Input contract.
- Output or side effects.
- Lease behavior.
- Retry limit.
- Backoff strategy.
- Timeout.
- Idempotency key.
- Dead-letter or terminal-failure handling.
- Observability.
## Claiming work
Concurrent workers must claim jobs safely using an approved locking or leasing pattern.
Duplicate execution must not corrupt data or produce duplicate authoritative records.
## Retry state
Retry attempts, last error category, next attempt time, and terminal state must be stored explicitly when operationally necessary.
Raw exception messages must not be treated as stable machine-readable state.
# Security standards
## Least privilege
Each service and worker must use a database role with only the permissions it requires.
Do not share one unrestricted production credential across the application, workers, analytics, and administration.
## Secrets
Database credentials must come from approved secret management or centralized configuration.
Credentials, connection strings, and sensitive values must never be committed to source control or printed in logs.
## Row-level authorization
User-specific data access must enforce ownership and authorization at a reliable boundary.
Where appropriate, use PostgreSQL row-level security or equally strong repository and service enforcement with dedicated tests.
## Sensitive data
Sensitive fields must be minimized, encrypted where required, excluded from logs, and protected from broad analytics access.
# Observability and operations
## Required metrics
Production databases and critical tables must be monitored for:
- Connection usage.
- Query latency.
- Error rate.
- Deadlocks.
- Lock waits.
- Transaction duration.
- Replication lag where applicable.
- Storage growth.
- Index growth.
- Cache hit ratio.
- Vacuum health.
- Slow queries.
- Failed migrations.
- Worker backlog.
- Data freshness.
## Structured database logging
Repository and worker logs must provide enough context to diagnose failures without exposing secrets or personal data.
Include where appropriate:
- Operation name.
- Table or repository name.
- Correlation or job identifier.
- Duration.
- Rows affected.
- Retry state.
- Error category.
Do not log complete financial payloads, personal records, credentials, or raw SQL parameters when sensitive.
## Alerts
Alerts must be actionable and tied to an owner and runbook.
Alert on customer impact, data staleness, failed ingestion, persistent job backlog, migration failure, and dangerous capacity conditions—not merely every transient database warning.
# Backup, recovery, and disaster readiness
## Backup requirements
Every authoritative database must have documented:
- Backup frequency.
- Retention period.
- Encryption.
- Storage location.
- Recovery Point Objective.
- Recovery Time Objective.
- Restore procedure.
- Restore-test schedule.
A backup is not considered valid until restoration has been tested.
## Point-in-time recovery
Critical databases should support point-in-time recovery where required by business risk.
## Rebuildability
Derived and analytical databases must document whether they can be fully rebuilt from authoritative sources and how long rebuilding is expected to take.
# Testing standards
Database changes must include tests appropriate to the risk:
- Migration tests.
- Repository unit or integration tests.
- Constraint tests.
- Transaction rollback tests.
- Concurrency tests.
- Idempotency tests.
- Pagination tests.
- Query-plan tests for critical paths.
- Data-quality tests.
- Historical point-in-time tests.
- Permission and authorization tests.
- Backup and restore exercises.
Every production database defect must receive a regression test where practical.
# Pull-request database checklist
Every database-related pull request must answer:
- Which database owns this data?
- Who is the authoritative writer?
- Is the data authoritative, derived, cached, or analytical?
- Why is a schema change necessary?
- Were existing tables or fields considered?
- What are the expected read and write patterns?
- What constraints enforce correctness?
- Which indexes support the queries?
- What is the growth and retention expectation?
- Is the migration backward-compatible?
- Can it be rolled back or recovered safely?
- Could it lock a large table?
- Is a backfill required?
- How is the backfill resumed after failure?
- Are units, currency, time zone, and nullability documented?
- Is provenance preserved?
- Are authorization and privacy implications covered?
- Are monitoring and alerts included?
- Were representative query plans reviewed?
- Were tests added?
- Was unrelated schema cleanup avoided?
# AI comment-first database workflow
Before implementing any table, migration, query, repository, or persistence model, the AI must first write a short design comment or documentation block explaining:
- The responsibility of the database object.
- Why it is required.
- Existing alternatives considered.
- Data ownership.
- Read and write paths.
- Constraints.
- Indexing needs.
- Transaction behavior.
- Failure and retry behavior.
- Migration and rollback strategy.
- Retention and provenance.
The AI must then implement only the documented scope.
The AI must not create speculative tables, generic abstractions, premature partitioning, unnecessary stored procedures, duplicate indexes, or fields intended only for hypothetical future use.
# Prohibited patterns
The following are prohibited unless narrowly justified in an approved design document:
- Raw SQL in routes, controllers, UI components, or domain models.
- `SELECT *`.
- Unparameterized SQL.
- Missing constraints for known invariants.
- Untyped dictionary or tuple repository contracts.
- Naive timestamps.
- Monetary storage in floating-point types.
- Silent overwriting of historical financial data.
- Unbounded queries.
- Accidental N+1 queries.
- Schema changes outside migrations.
- Destructive migration and dependent code change in one unsafe deployment.
- Multiple undocumented authoritative writers.
- Hidden cross-database dependencies.
- Storing plausible defaults for missing financial data.
- Bare numeric status codes.
- Database credentials in source code or logs.
- Broad production roles with unnecessary privileges.
- Backups that have never been restored in a test.
- Comments added only after implementation instead of before design.
# Completion criteria
A database feature is not complete until all applicable items exist:
- Ownership defined.
- Schema documented.
- Migration created and tested.
- Recovery or rollback planned.
- Constraints implemented.
- Indexes reviewed.
- Query patterns documented.
- Repository contracts typed.
- Transactions and concurrency handled.
- Idempotency addressed.
- Provenance and freshness recorded.
- Retention and deletion policy defined.
- Authorization reviewed.
- Monitoring and alerts established.
- Backup or rebuild strategy documented.
- Tests passing.
- Documentation synchronized with implementation.
- Production verification plan prepared.
# Relationship to other engineering standards
This page must be loaded together with:
- Engineering Code Standards
- Python Engineering Standards
- JavaScript and TypeScript Engineering Standards
- Engineering Development and Operational Standards
- Relevant system-design and data-ingestion documentation
When rules conflict, choose the safer design and document the conflict before implementation.
