# Disaster-Recovery Drill

1. Declare a drill, record participants/start time, freeze releases, and create an isolated network and fresh credentials.
2. Select the latest eligible backup from the secondary region and record its timestamp and checksum.
3. Restore users, market, and analytics databases with `scripts/restore_test.sh` or the managed-service equivalent.
4. Verify schema versions, table/row counts, constraints, recent synthetic writes, and application startup.
5. Recover Redis as disposable infrastructure, run in-flight queue recovery, and warm only critical caches.
6. Run health, authentication, cached/cold analysis, screener, portfolio, and billing synthetic journeys.
7. Record actual RPO from the newest recovered write and RTO from declaration to successful journeys.
8. Exercise DNS/traffic cutover, monitor SLOs, then return to primary using the same verification gates.
9. Destroy drill credentials/data, retain sanitized evidence, and assign every gap an owner and due date.
