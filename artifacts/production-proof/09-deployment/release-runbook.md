# Release, Canary, and Rollback

1. Freeze the candidate by commit and artifact digest; confirm release gate, security scans, approvals, and current backup health.
2. Run `scripts/release-migrate.sh`; stop immediately on preflight or migration failure and preserve redacted output.
3. Deploy one canary web instance with workers paused. Verify health, version, database schemas, and internal telemetry.
4. Run synthetic login, screener, cached/cold analysis, portfolio, and billing journeys.
5. Send 5% traffic for 10 minutes, then 25% for 15 minutes. Compare errors, p95 latency, saturation, model failures, and billing integrity against baseline.
6. Promote only when no critical alert fires, error ratio stays below 1%, p95 regression stays below 20%, and integrity checks match.
7. On threshold breach, stop promotion, disable risky feature flags, and route traffic to the previous compatible artifact.
8. Let old workers finish acknowledged work within the platform grace period; interrupted Redis jobs recover on replacement startup.
9. Never reverse a destructive schema change in place. Deploy a backward-compatible corrective migration or invoke the tested restore procedure.
10. Observe full traffic for 30 minutes and archive artifact, migration, synthetic, canary, approval, and rollback-decision evidence.
