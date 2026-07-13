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

- SEC EDGAR is an authoritative, no-premium structured source for Canadian
  issuers that also file standardized annual XBRL with the SEC. This is useful
  for cross-listed coverage, but it is not a complete TSX/TSXV source.
- SEDAR+ provides public issuer profile and document search pages, but a stable
  public API equivalent to SEC CompanyFacts is not available here. SEDAR+'s
  public-site terms prohibit scraping and database construction, so the app
  must use the licensed SEDAR+ Data Distribution Service or verified issuer
  documents for TSX-only coverage.
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

## Direct SEC Import

For an eligible Canadian cross-listed issuer, no source files or database-load
script are required. The worker downloads the official SEC ticker identity,
submissions metadata, CompanyFacts payload and latest annual iXBRL document in
memory; validates Canadian identity, annual forms, taxonomy, currency, aligned
periods, balance reconciliation, shares and provenance; then writes canonical
rows and the screener projection directly to `DATABASE_MARKET_URL`.

Run:

```bash
python -m codes.workers.canada_ingest_worker --symbol SHOP.TO
```

If the SEC and Canadian symbols differ, pass the verified U.S. ticker:

```bash
python -m codes.workers.canada_ingest_worker --symbol ABX.TO --sec-ticker B
```

The worker rejects a ticker when EDGAR does not identify the resolved issuer as
Canadian. This prevents same-symbol collisions from importing another company.
It also refuses issuers without aligned annual XBRL or dated authoritative
shares. A refusal writes nothing and explains that the licensed SEDAR+/issuer
path is required.

Set `SEC_USER_AGENT` to the production application name and monitored contact
email before deployment, in accordance with SEC fair-access guidance. The
existing development fallback is not a production contact identity.

This route does not make the Canada market release-ready by itself. Canada
remains internal until the roadmap's issuer-count, audit, coverage, licensing,
redistribution and validation-rate gates pass.

## Verified CSV Import

The licensed-source ingestion boundary remains a verified CSV export bundle.
This is for licensed feed exports, issuer-extracted financial statements, or a
licensed SEDAR+ extraction job after it has produced structured facts. The
importer does not scrape SEDAR+ and does not write JSON data files.
Successful public-confidence imports write canonical facts and their screener
projection in one transaction, so the Canada tab is populated after refresh.

Run:

```bash
BUNDLE_DIR=/absolute/path/to/verified/SHOP.TO
python -m codes.workers.canada_ingest_worker \
  --symbol SHOP.TO \
  --company-csv "$BUNDLE_DIR/company.csv" \
  --periods-csv "$BUNDLE_DIR/periods.csv" \
  --documents-csv "$BUNDLE_DIR/documents.csv" \
  --facts-csv "$BUNDLE_DIR/facts.csv" \
  --shares-csv "$BUNDLE_DIR/shares.csv"
```

These optional files are not generated by the worker or bundled with the
repository because doing so would fabricate or redistribute source financial
records. They must be produced by a verified issuer or licensed source. Omit
all CSV arguments to use the direct SEC route above.

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
