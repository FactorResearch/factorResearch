# Germany Market Release Runbook

Branch: `germany`

Status: internal validation only. There is no Germany launch date. `DE` must
remain `false` in `feature_flags.json` until every gate below has written,
approved evidence. A passing import or a `public_score_ready` worker result is
not permission to enable, advertise, sell, or publish Germany coverage.

This file is the country-specific publication checklist for Germany. It is
separate from the general repository README and must be updated whenever the
Germany acquisition, licensing, scoring, or release process changes.

## What Is Implemented

- Stable screener route: `/screener/de`, with `/screener/germany` and
  `/screener/deutschland` aliases.
- Source-injected Germany adapter with canonical facts stored in shared typed
  PostgreSQL `market_*` tables using market code `DE`.
- No country database, country-specific table family, JSON file, or JSON column
  is used for durable Germany facts.
- CSV import worker for verified regulator, issuer, or licensed-source exports.
- Deterministic German-label mappings and explicit IFRS, EU-adopted IFRS, and
  HGB validation.
- Fail-closed validation for issuer identity, exchange, security type, source
  document, provenance, annual history, currency, dated shares, and balance
  reconciliation.

The current ordinary-share scoring bridge does not support ADRs or investment
trusts. It also does not provide Germany price-based outputs. Do not present
missing price, market-cap, momentum, or valuation data as zero or available.

## Do Not Launch While Blocked

Germany is a no-go until all of these are resolved:

- No written commercial right exists for each source's intended use: collection,
  storage, normalization, derived analytics, display, paid users, institutional
  users, user/device reporting, geographic distribution, retention, audit, and
  deletion.
- No approved production source pipeline exists for the target Germany universe.
  The committed worker starts from verified exports; it is not a bulk downloader
  or a public-web scraper.
- No approved issuer identity master links ticker, ISIN, LEI, company-register
  identifier, exchange, delistings, mergers, and cross-listings.
- No audited 50-issuer minimum coverage report exists with at least three annual
  periods where available, source links, accepted accounting mappings, and
  documented exclusions.
- No licensed price and corporate-action feed exists with quote currency, quote
  unit, adjustment state, timestamp, and redistribution rights.
- No final approval exists from Legal, Data, Engineering, Product, Security,
  and Operations.

Do not choose a launch date before these gates pass. The release is gate-based.

## Approved Source Boundary

Possible inputs require a documented rights review before production use:

- BaFin or other regulator-authoritative disclosure sources.
- Bundesanzeiger / Unternehmensregister records.
- Issuer annual reports and regulated disclosures.
- Deutsche Boerse listing, reference, corporate-action, or price data.
- A licensed vendor only where its contract covers source provenance and the
  application's actual commercial use.

Do not scrape public source websites. Public availability does not grant
commercial storage, redistribution, or derived-data rights. Recheck source
terms immediately before contracting because terms, products, and contacts can
change.

## Licensing Contact Directory

Contacts below were verified against official sites on 2026-07-13. Recheck them
immediately before sending a request or signing an agreement.

- Deutsche Borse Market Data + Services: email `data.services@deutsche-boerse.com`.
  Use the [Market Data + Services contact page](https://www.mds.deutsche-boerse.com/mds-en/contact).
  This is the commercial contact for Xetra/Frankfurt reference, price,
  corporate-action, display, redistribution, and derived-data rights.
- Deutsche Borse data-use approvals: email `mds.agreements@deutsche-boerse.com`.
  Use the [Data Usage Declaration and approval page](https://www.mds.deutsche-boerse.com/mds-en/real-time-data/data-usage-declaration)
  when the proposed product involves data-feed/API onward dissemination.
- BaFin, Bundesanzeiger, Unternehmensregister, and issuer sources: use their
  current official contact routes for filing-access and reuse questions. They
  are not substitutes for a Deutsche Borse market-data licence.

## Data Acceptance Contract

Only source exports with all files below may be imported:

- `company.csv`: `symbol,name,exchange,country,currency,regulator_id,security_type,accounting_standard`
- `periods.csv`: `symbol,fiscal_year,fiscal_period,period_end,currency`
- `documents.csv`: `document_id,source,url,filing_date,period_end,form,confidence`
- `facts.csv`: `symbol,statement_type,fact_name,fiscal_year,fiscal_period,period_end,currency,value,source_document_id,source_url,confidence,accounting_standard,extraction_method,normalization_method`
- `shares.csv`: `symbol,shares_outstanding,as_of,source`

`lei` or `register_number` may replace `regulator_id`. Allowed public confidence
states are `regulatory_verified`, `issuer_verified`,
`licensed_source_verified`, and `cross_checked`. The internal-only state
`provider_normalized_internal_only` needs `--allow-internal` and never creates
a public screener projection.

Supported accounting standards are `IFRS`, `EU-adopted IFRS`, and `HGB`. German
financial labels map only when a deterministic entry exists in
`codes/data/providers/germany_normalization.py`. Never relabel unknown facts to
pass validation.

## Internal Population

Initialize the normal market database once in the deployment environment:

```bash
set -a
source .env
set +a
PYTHONPATH=. python -c 'from codes.data import db; db.init_db(); print("market_schema_ready=true")'
```

Import one verified issuer bundle:

```bash
PYTHONPATH=. python -m codes.workers.germany_ingest_worker \
  --symbol SAP.DE \
  --bundle-dir /absolute/path/to/verified/SAP.DE
```

The worker checks every required file before writing. A failed validation must
leave no partial source facts or stale public screener row. Inspect the quality
report and source-document links in the market database before counting an
issuer toward release coverage.

For local internal validation only, set `DE` to `true`, restart the app, and
open `/screener/de`. Restore `DE` to `false` before committing, deploying, or
opening a production environment.

## Required Release Evidence

Create and retain a private Germany release dossier containing:

1. Signed or counsel-approved source contracts and terms analysis for every
   source and every product tier/territory.
2. Source architecture, credentials ownership, rate limits, retries, monitoring,
   retention/deletion policy, and incident process.
3. Ticker/ISIN/LEI/register identity master plus duplicate, renamed, delisted,
   merger, and dual-listing controls.
4. A 50-issuer coverage report with source-to-output audit samples, three-year
   history checks, accepted German-label and IFRS/HGB mappings, exclusions, and
   failure-rate thresholds.
5. Tests proving that weak provenance, unsupported labels, mismatched currency,
   unsupported security type, missing shares, restatements, and unreconciled
   balance sheets refuse scoring.
6. Licensed quote and corporate-action evidence before any price-based result is
   exposed.
7. Desktop and mobile checks for routing, empty state, source/confidence copy,
   currency display, stale data, errors, and disabled-market behavior.
8. Production-like backup/restore evidence and successful required test suite.
9. Written Legal, Data, Engineering, Product, Security, and Operations sign-off.

## Licensing Inquiry Template

Send the following through each source's current official licensing or business
contact route. Keep the response, contract, and counsel review in the private
release dossier.

Subject: `Commercial Germany equity-data licence for research application`

```text
Hello,

We operate a commercial web-based equity research application and are assessing
Germany market coverage. We require written terms and pricing for issuer,
filing, reference, corporate-action, and delayed or end-of-day price data, as
applicable to your service.

Our application stores normalized records in its backend and displays source
and derived analytics to free, paid, professional, and institutional users who
may be located inside or outside Germany. Please confirm licences, attribution,
reporting, audit, retention/caching, derived-data, redistribution, user/device,
geographic, and deletion obligations for this use.

Germany support will remain disabled until the review is complete.

Regards,
[Name]
[Company]
[Contact details]
```

## Enablement Sequence

1. Merge the approved Germany implementation into `main` with `DE=false`.
2. Complete every item in the private release dossier and obtain written
   cross-functional approval.
3. Run the approved production ingestion job and validate the coverage report.
4. Deploy with `DE=false`; verify migrations, quality reports, source evidence,
   backup/restore, and disabled-market behavior.
5. Obtain final release approval for the exact deployment revision.
6. Change only `DE` to `true`, deploy, and verify `/screener/de` on desktop and
   mobile with production data.
7. Publish release notes describing coverage, exclusions, sources, confidence,
   and any unavailable price-based outputs. Do not claim full Germany coverage
   beyond the approved universe.
8. Tag the approved release commit and archive the release dossier.

## Branch Files

- `codes/data/providers/germany.py`: provider adapter and symbol handling.
- `codes/data/providers/germany_ingestion.py`: verified bundle parser.
- `codes/data/providers/germany_db.py`: relational persistence and projection.
- `codes/data/providers/germany_normalization.py`: scoring bridge and gates.
- `codes/workers/germany_ingest_worker.py`: import command.
- `docs/track_b_germany.md`: engineering implementation notes.
- `docs/release_germany.md`: user-facing branch release notes.
