# Recovery Policy

| Data class | Authority | Target RPO | Target RTO | Recovery |
|---|---|---:|---:|---|
| Accounts, subscriptions, usage | users PostgreSQL | 15 minutes | 2 hours | encrypted backup plus point-in-time recovery |
| Market facts and persisted scores | market PostgreSQL | 24 hours | 4 hours | encrypted backup; refetch public source data where licensed |
| Analysis snapshots and analytics | analytics PostgreSQL | 1 hour | 4 hours | encrypted backup; rebuild derived snapshots when provenance permits |
| Redis jobs and locks | PostgreSQL/application requests | best effort | 30 minutes | recover in-flight jobs, then requeue idempotently |
| Filesystem/provider caches | upstream authoritative source | none | 1 hour | discard and warm gradually |
| Configuration and code | version control/artifact registry/secrets manager | one release | 1 hour | redeploy immutable artifact and injected secrets |

Backups must be encrypted, access logged, immutable for the approved retention window, and stored outside the primary failure domain. Production credentials must never be restored into drill environments. Account-deletion data ages out with backup retention; legal holds require documented approval.
