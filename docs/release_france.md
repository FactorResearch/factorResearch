# France Branch Release Notes

Branch: `france`

Status: internal validation only. France has no launch date and `FR` remains
disabled in `feature_flags.json`.

## Added

- Feature-gated France screener route at `/screener/fr`, plus France and
  Euronext Paris aliases.
- Source-injected France adapter and shared relational market-database source.
- Verified-source CSV ingestion:

  ```bash
  PYTHONPATH=. python -m codes.workers.france_ingest_worker \
    --symbol AI.PA --bundle-dir /absolute/path/to/verified/AI.PA
  ```

- Explicit IFRS, EU-adopted IFRS, and French GAAP validation.
- Deterministic mappings for approved French financial-statement labels.
- Provenance, dated shares, Euronext Paris listing, ordinary-share,
  annual-history, reporting-currency, and balance-sheet-reconciliation gates.

## Integrity And Release Boundary

All durable France data is stored in typed relational market tables, not JSON
files or JSON columns. Provider-only facts cannot create a public screener row.
Unknown labels or weak source evidence fail closed. Public release requires the
licensing, source audit, coverage, price-data, and organization sign-offs in
`README_FRANCE.md`.
