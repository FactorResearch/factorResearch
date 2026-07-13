# UK Branch Release Notes

Branch: `uk`

Status: internal validation only. There is no UK launch date, and the committed
`GB` market flag remains disabled.

## Added

- Feature-gated United Kingdom screener navigation at `/screener/gb`, with
  `/screener/uk` and `/screener/united-kingdom` aliases.
- A source-injected UK provider adapter and database-backed runtime source.
- Relational storage of UK issuer identity, Companies House/regulator ID,
  security type, accounting standard, fiscal periods, statement facts,
  documents, shares, quality issues, and screener projections.
- Verified-source CSV ingestion for Companies House, FCA NSM, issuer annual
  reports, and licensed feeds:

  ```bash
  python -m codes.workers.uk_ingest_worker \
    --symbol VOD.L \
    --bundle-dir /absolute/path/to/verified/VOD.L
  ```

- Direct `.L` analysis routing from verified market-database facts, without
  requiring users to rerun or reimport existing analysis when projections are
  added or versioned.
- Explicit IFRS, UK-adopted IFRS, UK GAAP, FRS 101, and FRS 102 validation.
- Explicit ordinary-share, ADR, and investment-trust classification. ADRs and
  investment trusts fail closed pending dedicated models.
- Multi-currency statement support with rejection of mixed-currency history.
- A GBX/GBP safety gate that withholds UK price-based calculations until a
  licensed quote source supplies explicit currency and quote-unit metadata.

## Data Integrity

- UK market data is not persisted in JSON files or JSON database columns.
- Provider-only data cannot pass public confidence checks.
- Every scored required fact must reference a stored source document and carry
  accepted accounting-standard and confidence metadata.
- Failed imports persist their quality report but do not publish a screener row;
  stale public projections are removed atomically.
- Canada and U.S. routing remain backward compatible and independently gated.

## Before Public Release

- Approve commercial reuse terms for each Companies House, FCA NSM, issuer, or
  licensed input used by production.
- Execute the required LSE issuer/reference/market-data licence and document
  display, derived-data, retention, audit, and user-tier rights.
- Build and approve a production bulk extraction adapter; public web scraping
  is not an acceptable population strategy.
- Validate identity, filing currency, accounting taxonomy, amendments,
  restatements, shares, and source links across the release audit universe.
- Add licensed quote currency/unit metadata before enabling valuation outputs.
- Obtain written legal, data, engineering, product, and operations sign-offs.
