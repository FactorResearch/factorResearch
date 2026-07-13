# Canada Branch Release Notes

Status: internal validation; not approved for public Canada-market launch.
There is no Canada launch date, and the committed market flag remains disabled.

## Added

- Feature-flagged Canada screener routing with a stable `/screener/ca` URL.
- Shared relational international-market storage keyed by `market_code`, kept
  separate from user/account data.
- Canonical Canadian issuer, fiscal-period, statement-fact, source-document,
  shares, quality-report and typed screener-projection records.
- Automatic projection backfill for verified data, so new release features do
  not require users to rerun analysis or reimport source facts.
- One-command official SEC ingestion for eligible Canadian cross-listed
  issuers:

  ```bash
  python -m codes.workers.canada_ingest_worker --symbol SHOP.TO
  ```

- IFRS and US-GAAP normalization, CAD/USD reporting-currency detection,
  restatement-aware annual period selection, class-level share extraction,
  per-period provenance, balance reconciliation and strict no-score failures.
- Backward-compatible verified CSV ingestion for licensed SEDAR+ or verified
  issuer-document extraction jobs.

## Data Integrity

- Market payloads and screener projections are not persisted in JSON files or
  JSON database columns.
- Same-symbol SEC collisions are rejected unless EDGAR identifies the issuer as
  Canadian; different dual-list symbols require an explicit `--sec-ticker`.
- Provider-only fundamentals do not pass the public confidence gate.
- Failed or incomplete imports do not publish a row and remove stale public
  projections for that issuer.

## Before Public Release

- Obtain licensed full-market SEDAR+ distribution or an approved verified
  issuer-document source. Public SEDAR+ pages must not be scraped.
- Validate at least 50 large/liquid issuers with at least three fiscal years
  where available.
- Complete manual audit sampling, coverage/pass-rate reporting, unsupported
  issuer documentation, redistribution review and user-facing source display.
- Configure `SEC_USER_AGENT` with the production application identity and a
  monitored contact email.
