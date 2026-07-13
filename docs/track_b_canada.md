# Track B Canada Notes

Branch: `canada`

## Scope

This branch starts Track B with Canada as the first Tier 1 market. It adds the
Canada provider adapter and feature-gated market wiring without coupling the
analysis engines to Canadian provider payloads.

## Release Switch

Canada is controlled by `feature_flags.json`.

Enable it with:

```json
{
  "markets": {
    "US": true,
    "CA": true
  }
}
```

The screener market navigation will show Canada only when `CA` is enabled.
Canada has the canonical route `/screener/ca`; refreshing, bookmarking or
sharing that route must retain the Canada market. The route selects the market
but does not bypass Canada data-quality or release gates.

## Market Routing Contract

- Market UI metadata lives in the typed registry at
  `codes/app_modules/screener_markets.py`.
- The URL is the selected-market state; no callback or browser store owns it.
- Unknown or disabled market routes resolve to the enabled default market.
- Future markets add registry metadata and a feature flag. They do not add a
  market-specific table callback.
- Provider adapters, canonical facts and provenance remain separate from the
  UI registry, so enabling navigation cannot make unverified data scoreable.

## Data Sourcing Issues

- SEDAR+ provides public issuer profile and document search pages, but a stable
  public API equivalent to SEC CompanyFacts is not currently wired here.
- Canadian filings often provide annual/interim reports as PDFs or issuer
  documents, so structured fundamentals may require a licensed feed, a
  document-ingestion pipeline, or an internal normalized database.
- TSX/TSXV listings, symbols, company metadata and shares outstanding may need
  separate exchange or market-data licensing.
- FX is display-only under the roadmap. CAD/USD conversion must not change
  Graham, Buffett, Piotroski, Altman, portfolio weights or risk calculations.
- Cost risk: Canadian fundamentals are likely cheap to prototype through
  cached/manual ingestion, but expensive to automate reliably at scale unless
  a provider with redistribution rights is licensed.

## Implementation Rule

Production data should be connected by implementing `CanadaDataSource` and
injecting it into `CanadaProviderAdapter`. Do not add SEDAR+ scraping to model
or analysis code.

## Current Storage Path

- Runtime Canada reads use `CanadaDatabaseDataSource`, which pulls normalized
  issuer, period, statement fact, filing document, shares, and provenance rows
  from the market database.
- All countries use the database configured by `DATABASE_MARKET_URL`; user and
  account state remains in `DATABASE_USERS_URL`.
- Country data shares normalized relational tables keyed by `market_code`:
  `market_issuers`, `market_fiscal_periods`, `market_statement_facts`,
  `market_source_documents`, `market_shares_outstanding`,
  `market_quality_reports`, and `market_quality_issues`.
- Public, quality-approved screener projections use typed columns in
  `market_screener_rows`. No market payload or screener row is persisted as a
  JSON file or JSON database column.
- Existing `canada_*` tables are copied into the generic tables idempotently at
  database initialization. They remain untouched as rollback data, and missing
  public screener rows are calculated from those verified facts at app startup.
  Screener rows carry a projection version; bumping it recalculates stale rows
  from canonical facts without a user analysis rerun or source re-import.
- New Canada data should enter through `ingest_verified_canada_financials()`
  after source extraction has produced canonical financials with filing
  documents and per-fact provenance.
- Provider-normalized data remains internal-only unless explicitly ingested
  with `allow_internal=True`; public scoring requires verified source
  confidence and validation gates to pass.

## Database Boundary

Use one physical market database and shared tables keyed by `market_code` for
Canada, the United States, the United Kingdom, France, and later markets. This
keeps cross-market queries and migrations consistent without creating a pool,
backup job, and schema lifecycle for every country. PostgreSQL table
partitioning by `market_code` can be added when measured volume requires it.

Use a separate physical country database only when a source licence prohibits
co-mingling, a jurisdiction imposes data-residency requirements, or production
load demonstrates that independent scaling is necessary. Provider adapters and
the market-code storage API preserve that future split boundary.

## Verified CSV Import

The first production ingestion boundary is a verified CSV export bundle. This
is for licensed feed exports, issuer-extracted financial statements, or an
internal SEDAR+ document extraction job after it has produced structured facts.
The importer does not scrape SEDAR+ and does not write JSON data files.
Successful public-confidence imports write canonical facts and their screener
projection in one transaction, so the Canada tab is populated after refresh.

Run:

```bash
python -m codes.workers.canada_ingest_worker \
  --symbol SHOP.TO \
  --company-csv company.csv \
  --periods-csv periods.csv \
  --documents-csv documents.csv \
  --facts-csv facts.csv \
  --shares-csv shares.csv
```

Required files:

- `company.csv`: `symbol,name,exchange,country,currency`
- `periods.csv`: `symbol,fiscal_year,fiscal_period,period_end,currency`
- `documents.csv`: `document_id,source,url,filing_date,period_end,form,confidence`
- `facts.csv`: `symbol,statement_type,fact_name,fiscal_year,fiscal_period,period_end,currency,value,source_document_id,source_url,confidence,accounting_standard,extraction_method,normalization_method`
- `shares.csv`: `symbol,shares_outstanding,as_of,source`

Allowed `statement_type` values are `income`, `balance`, and `cash_flow`.
Allowed confidence values are `regulatory_verified`, `issuer_verified`,
`licensed_source_verified`, `cross_checked`, and
`provider_normalized_internal_only`.
