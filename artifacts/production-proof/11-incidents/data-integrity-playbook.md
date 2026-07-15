# Financial Data and Model Integrity Incident

1. Declare scope by model version, provider, ticker/market, analysis time, and persisted snapshot provenance.
2. Disable the affected model/provider or cold-analysis path; label known stale results and preserve prior versions for comparison.
3. Stop bulk recomputation until the defect, affected population, and authoritative source are proven.
4. Compare golden sets, invariants, source filings, cached payloads, and a representative affected sample.
5. Deploy a versioned correction, recompute a bounded sample, then backfill idempotently with progress and failure telemetry.
6. Identify users/results materially affected and involve communications/legal before silently replacing published output.
7. Close only after corrected results, provenance, historical records, and downstream screener/portfolio behavior are verified.
