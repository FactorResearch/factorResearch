# Germany Branch Release Notes

Branch: `germany`

Status: internal validation only. Germany has no launch date and `DE` remains
disabled in `feature_flags.json`.

## Added

- Feature-gated Germany screener route at `/screener/de`, plus Germany and
  Deutschland aliases.
- Source-injected Germany adapter and shared relational market-database source.
- Verified-source CSV ingestion:

  ```bash
  PYTHONPATH=. python -m codes.workers.germany_ingest_worker \
    --symbol SAP.DE --bundle-dir /absolute/path/to/verified/SAP.DE
  ```

- Explicit IFRS, EU-adopted IFRS, and HGB validation.
- Deterministic mappings for approved German financial-statement labels.
- Provenance, dated shares, exchange/security classification, annual-history,
  reporting-currency, and balance-sheet-reconciliation gates.

## Integrity And Release Boundary

All durable Germany data is stored in typed relational market tables, not JSON
files or JSON columns. Provider-only facts cannot create a public screener row.
Unsupported labels or source evidence fail closed. Public release requires the
licensing, source audit, coverage, price-data, and organization sign-offs in
`docs/track_b_germany.md`.
