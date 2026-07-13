# Netherlands Market Release Runbook

Branch: `netherlands`

Status: internal validation only. There is no Netherlands launch date. `NL` must
remain `false` in `feature_flags.json` until every release gate has written,
approved evidence.

## What Is Implemented

- Feature-gated screener routes `/screener/nl` and `/screener/netherlands`.
- Source-injected Euronext Amsterdam adapter for `NL` symbols such as `ASML.AS`.
- Typed relational persistence in shared PostgreSQL `market_*` tables; no
  country database, durable JSON file, or JSON column.
- Verified CSV importer and deterministic Dutch/IFRS fact mappings.
- Fail-closed checks for issuer identity, Euronext Amsterdam listing, ordinary
  shares, provenance, three annual periods, currency, dated shares, and
  balance-sheet reconciliation.

## Release Blockers

Do not launch until AFM/issuer-source rights, Euronext Amsterdam market-data
rights, and a cross-listing identity master are approved in writing where the
source terms require it. The identity master must link ticker, ISIN, LEI,
issuer, listing venue, delistings, mergers, and cross-listings. No price,
market-cap, momentum, or valuation output may be presented until a licensed
price and corporate-action source provides explicit currency, unit, timestamp,
adjustment, and redistribution rights.

## Data And Local Import

The five UTF-8 CSVs are `company.csv`, `periods.csv`, `documents.csv`,
`facts.csv`, and `shares.csv`; schemas are in `docs/track_b_netherlands.md`.
Initialize the normal market database, then import a verified bundle:

```bash
PYTHONPATH=. python -c 'from codes.data import db; db.init_db(); print("market_schema_ready=true")'
PYTHONPATH=. python -m codes.workers.netherlands_ingest_worker --symbol ASML.AS --bundle-dir /absolute/path/to/verified/ASML.AS
```

For local validation only, set `NL` to `true`, restart the app, and visit
`/screener/nl`. Restore `NL=false` before committing or deploying.

## Licensing Inquiry

Send the source-specific request through the current official licensing route;
keep replies, terms, and contracts in the private release dossier. Ask about
storage, normalization, derived analytics, display, paid/professional/
institutional users, redistribution, territory, reporting, audit, retention,
and deletion. Public availability does not itself grant those rights.

## Enablement

1. Merge with `NL=false`.
2. Complete a 50-issuer audited coverage and cross-listing identity report.
3. Obtain Legal, Data, Engineering, Product, Security, and Operations approval.
4. Load and audit production data while `NL=false`.
5. Approve the deployment revision, enable only `NL`, and verify desktop/mobile
   Netherlands screener behavior.
