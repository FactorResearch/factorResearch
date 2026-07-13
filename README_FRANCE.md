# France Market Release Runbook

Branch: `france`

Status: internal validation only. There is no France launch date. `FR` must
remain `false` in `feature_flags.json` until every release gate below has
written approval. A passing import is not permission to enable, advertise,
sell, or publish France coverage.

## What Is Implemented

- Feature-gated France screener route: `/screener/fr`, with `/screener/france`
  and Paris/Euronext aliases.
- Source-injected France adapter and `FR` market registry entry.
- Typed relational persistence in shared PostgreSQL `market_*` tables. No
  France JSON file, JSON column, country database, or per-visit persistence.
- Verified CSV import worker and deterministic French-label mappings.
- Fail-closed checks for issuer identity, Euronext Paris listing, ordinary
  shares, source documents, provenance, three annual periods, currency, dated
  shares, accounting standard, and balance-sheet reconciliation.

This release foundation provides fundamental scoring only. It does not grant
price, market-cap, corporate-action, momentum, or valuation coverage. Never
represent unavailable outputs as zero or supported.

## Do Not Launch While Blocked

- There is no written commercial right for the intended acquisition, storage,
  normalization, derived analytics, display, paid/professional/institutional
  use, redistribution, retention, audit, reporting, and deletion.
- There is no approved production pipeline based on AMF, Euronext Paris, issuer
  documents, or a licensed source. The committed worker imports verified
  exports; it does not scrape public websites.
- There is no approved issuer identity master joining ticker, ISIN, LEI, AMF
  identifier, Euronext instrument, corporate actions, delistings, and
  cross-listings.
- There is no audited 50-issuer coverage report with source links, three annual
  periods, accepted French/IFRS mappings, quality results, and exclusions.
- There is no licensed price and corporate-action source with redistribution
  rights and clear currency, unit, adjustment, and timestamp semantics.
- Legal, Data, Engineering, Product, Security, and Operations have not all
  signed the release dossier.

## Approved Source Boundary

Potential inputs require a written rights review before production use:

- AMF disclosures and approved filing access methods.
- Euronext Paris listing, reference, corporate-action, or price products.
- Issuer universal registration documents, annual reports, and regulated news.
- Licensed vendors only where the contract covers the application's actual
  commercial use and preserves source provenance.

Public availability is not a commercial-data licence. Do not scrape source
sites; recheck current terms and product contacts before contracting.

## Data Contract And Import

Each issuer bundle must contain `company.csv`, `periods.csv`, `documents.csv`,
`facts.csv`, and `shares.csv`. Required fields are documented in
`docs/track_b_france.md`. `regulator_id`, `lei`, or `amf_id` identifies the
issuer. Public confidence states are `regulatory_verified`, `issuer_verified`,
`licensed_source_verified`, and `cross_checked`.

Initialize the normal market database once, then import a verified bundle:

```bash
set -a
source .env
set +a
PYTHONPATH=. python -c 'from codes.data import db; db.init_db(); print("market_schema_ready=true")'
PYTHONPATH=. python -m codes.workers.france_ingest_worker --symbol AI.PA --bundle-dir /absolute/path/to/verified/AI.PA
```

For local validation only, set `FR` to `true`, restart the app, and open
`/screener/fr`. Restore `FR=false` before committing or deploying.

## Licensing Inquiry Template

Subject: `Commercial France equity-data licence for research application`

```text
Hello,

We operate a commercial web-based equity research application and are assessing
France market coverage. Please provide written terms and pricing for issuer,
filing, reference, corporate-action, and delayed or end-of-day price data.

Our application stores normalized records and displays source and derived
analytics to free, paid, professional, and institutional users worldwide.
Please confirm attribution, reporting, audit, retention/caching, derived-data,
redistribution, user/device, geographic, and deletion requirements.

France support remains disabled until this review is complete.

Regards,
[Name]
[Company]
[Contact details]
```

## Enablement Sequence

1. Merge with `FR=false`.
2. Complete the release dossier and obtain written cross-functional approval.
3. Run the approved production ingestion and validate the coverage report.
4. Deploy with `FR=false`; verify data quality, backup/restore, and disabled
   route behavior.
5. Approve the exact deployment revision, change only `FR` to `true`, deploy,
   and verify desktop and mobile France screeners.
6. Publish coverage, exclusions, data confidence, and unavailable outputs in
   release notes. Tag the release and archive the private dossier.
