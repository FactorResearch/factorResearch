# Track B Canada Notes

Branch: `canada`

## Scope

This branch starts Track B with Canada as the first Tier 1 market. It adds the
Canada provider adapter and feature-gated market wiring without coupling the
analysis engines to Canadian provider payloads.

## Release Switch

Canada is disabled by default.

Enable it with:

```bash
ENABLED_MARKETS=US,CA
```

The screener country selector will show Canada only when `CA` is enabled.

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
- Canada facts are stored in relational tables:
  `canada_issuers`, `canada_fiscal_periods`, `canada_statement_facts`,
  `canada_source_documents`, `canada_shares_outstanding`,
  `canada_quality_reports`, and `canada_quality_issues`.
- New Canada data should enter through `ingest_verified_canada_financials()`
  after source extraction has produced canonical financials with filing
  documents and per-fact provenance.
- Provider-normalized data remains internal-only unless explicitly ingested
  with `allow_internal=True`; public scoring requires verified source
  confidence and validation gates to pass.
