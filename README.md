# Graham Score / Factor Research

Graham Score is a PostgreSQL-backed equity research application with screening,
company analysis, factor research, portfolio analytics, simulations, and market
expansion through provider-neutral financial models.

## V2.2 Branch Scope

This release branch adds CAPM, Fama-French 3/5, and Carhart 4 research using
monthly factor returns, including return attribution and rolling exposures.
Existing saved analyses derive a CAPM view from their stored stock and SPY
histories when full V2.2 fields are unavailable.

## Release Status

> **CANADA IS INTERNAL-ONLY. THERE IS NO CANADA LAUNCH DATE.**
>
> Do not advertise, sell, promise, enable, or publish Canada support until every
> Canada release gate in this README has written evidence and final approval.

The committed default in `feature_flags.json` is:

```json
{
  "markets": {
    "US": true,
    "CA": false
  }
}
```

Keep `CA` set to `false` in every public branch and deployment. A successful
worker message such as `public_score_ready` means that one issuer passed the
fact-level source and quality checks. It does **not** mean the Canada product is
licensed, complete, audited, or approved for release.

The Canada code currently supports internal validation of eligible SEC-filed
Canadian issuers and imports from verified licensed-source exports. It does not
yet provide full TSX/TSXV coverage or complete Canada product parity.

## Current Canada Blockers

Canada is a no-go while any item below remains true:

- No executed SEDAR+ Data Distribution Service agreement, or equivalent
  licensed source agreement, is recorded in the private release dossier.
- No executed licence for the required TSX/TSXV issuer master, symbol status,
  corporate actions, and price/market data is recorded.
- The only automatic regulator path is SEC EDGAR, which covers an authoritative
  but incomplete subset of Canadian cross-listed issuers.
- There is no licensed, production bulk-ingestion adapter for full SEDAR+
  coverage. The licensed-source path currently starts at verified CSV exports.
- Canada has not passed the minimum 50-issuer audit and coverage gate.
- Direct Canada company analysis does not yet have complete market-provider
  parity with the U.S. analysis route.
- Canada source and confidence details are not yet complete in every public
  user workflow.
- The full repository test suite is not green. Focused Canada tests passing is
  necessary but not sufficient.
- `scripts/restore_test.sh` still contains placeholder database/table mappings
  and must not be treated as proof that production backups are restorable.
- Final legal, data, engineering, product, and operations sign-offs do not
  exist.

Do not add a launch date to this file. Launch is gate-based, not date-based.

## Current Repository Publication Blockers

These blockers apply even if Canada remains disabled:

- The repository has no `LICENSE` file. Do not make it public until the owner
  and counsel choose and approve either a proprietary distribution policy or a
  specific open-source licence.
- There is no approved third-party dependency or asset inventory and no
  `THIRD_PARTY_NOTICES` file.
- Ownership and permitted commercial use of `assets/logo.png` have not been
  recorded in the private release dossier.
- The complete test suite is not green, and CI currently runs only selected
  security and dependency checks rather than the complete suite.
- Production backup restoration has not been proven against the actual
  schemas.

Licensing and contact references in this README were last checked on
2026-07-13. That is a documentation review date, not a Canada launch date.
Terms, contacts, products, and prices can change; verify them again immediately
before signing an agreement or approving a release.

## Repository Map

- `codes/app.py`: Dash/Flask application entry point.
- `codes/data/db.py`: PostgreSQL market and user schemas.
- `codes/data/providers/`: provider-neutral and country-specific adapters.
- `codes/data/providers/canada_sec.py`: authoritative SEC path for eligible
  Canadian cross-listed issuers.
- `codes/workers/canada_ingest_worker.py`: Canada acquisition/import CLI.
- `feature_flags.json`: application tier and market visibility switches.
- `docs/track_b_canada.md`: Canada architecture and ingestion details.
- `docs/release_canada.md`: Canada branch release notes.
- `roadMap.md`: product and country release standards.
- `Publish.md`: broader pre-launch work.
- `SECURITY_CHECKLIST.md`: security controls and outstanding validation.

## Country Branch Workflow

Country code and country launch state are separate concerns. A merged adapter
does not release a market while its flag remains `false`.

Use this workflow for every new country:

1. Put provider-neutral schema, routing, cache, analysis, and UI fixes in
   `main` first, with all unreleased market flags disabled.
2. Create the country branch from the latest `main` using the lowercase branch
   name specified in `roadMap.md`.
3. Keep only that country's adapter, normalization, acquisition, flag entry,
   asset, tests, runbook, and release notes in the country branch.
4. Merge `main` into every active country branch when shared fixes land. Do not
   copy the same fix independently into each branch.
5. Merge completed country code into `main` with its market flag still `false`.
   Enable one market only after its own release gates and written approvals
   pass; other countries remain dormant and can launch in a different order.

For a new branch:

```bash
git switch main
git pull --ff-only
git switch -c <country-branch>
```

For an already-published country branch, preserve its history and bring shared
work forward with:

```bash
git switch <country-branch>
git merge main
```

Rebase only local, unpublished country work. Never rewrite a shared remote
country branch merely to make its graph look cleaner.

## Local Setup

### Prerequisites

- Python 3.11 or newer.
- PostgreSQL and PostgreSQL client tools.
- Redis for production session/rate-limit consistency. Local development can
  use the documented in-memory fallback.
- A real, monitored contact address for SEC automated access.

### Install

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Databases

Production should use separate physical databases for market data, user data,
and analytics. A jobs database is also expected by the backup tooling, although
the application does not currently initialize a jobs schema.

Example local creation:

```bash
createdb factorresearch_market
createdb factorresearch_users
createdb factorresearch_analytics
createdb factorresearch_jobs
```

Create `.env` in the repository root. `.env` is gitignored and must never be
committed.

```dotenv
FLASK_ENV=development
APP_FEATURE_FLAG=INTERNAL
FLASK_SECRET_KEY=replace-with-a-long-random-secret

DATABASE_MARKET_URL=postgresql://localhost/factorresearch_market
DATABASE_USERS_URL=postgresql://localhost/factorresearch_users
DATABASE_ANALYTICS_URL=postgresql://localhost/factorresearch_analytics
DATABASE_JOBS_URL=postgresql://localhost/factorresearch_jobs

REDIS_URL=redis://localhost:6379/0

# SEC asks automated clients to identify the organization and a contact.
SEC_USER_AGENT="Your Legal Company Name monitored-contact@your-domain.example"

# Optional: enables ticker logos in analysis, screener, Quick Peek, and portfolio.
# Logo.dev's free commercial tier requires the attribution rendered by the app.
LOGO_DEV_PUBLISHABLE_KEY=pk_replace_with_your_publishable_key
```

Do not use the same production URL for `DATABASE_MARKET_URL` and
`DATABASE_USERS_URL`. Store production credentials in the deployment platform's
secret manager, not in a deployed `.env` file.

Initialize the schemas used by the current application:

```bash
set -a
source .env
set +a

PYTHONPATH=. python -c \
  'from codes.data import db; db.init_db(); db.init_user_db(); print("market_and_user_schema_ready")'

PYTHONPATH=. python -c \
  'from codes.data.analytics_db import ensure_schema; ensure_schema(); print("analytics_schema_ready")'
```

Run locally:

```bash
PYTHONPATH=. python -m codes.app
```

The production process declared by `Procfile` is:

```bash
gunicorn --bind 0.0.0.0:${PORT:-8050} codes.app:server
```

Authentication must use a configured production provider and HTTPS. See
`AUTHENTICATION_SETUP.md` for provider-specific settings. Session UUID fallback
is for local development only.

### Analysis performance

- `ANALYSIS_BACKGROUND_JOBS=1` enables shared-context refresh and popular-stock precomputation. Set it on exactly one designated process, not every web worker.
- `PRECOMPUTE_SYMBOLS=AAPL,MSFT` selects high-traffic symbols; otherwise cached symbols are refreshed.
- `PRECOMPUTE_LIMIT=20` bounds each maintenance pass.
- `ANALYSIS_REFRESH_SECONDS=3600` controls maintenance frequency, with a five-minute minimum.
- `ANALYSIS_MAX_AGE_SECONDS=2592000` marks versioned records stale after 30 days while still serving them immediately.
- `COMOMENTUM_WORKERS=4` bounds parallel market-history retrieval.

## Internal Canada Development

To expose Canada locally, temporarily change `CA` to `true` in
`feature_flags.json`, restart the app, and use `/screener/ca`.

Before committing or deploying, set `CA` back to `false` and verify:

```bash
PYTHONPATH=. python -c \
  'from codes.core.app_flags import is_market_enabled; assert not is_market_enabled("CA"), "Canada must remain disabled"; print("canada_disabled=true")'
```

The expected public-safe value is always `"CA": false` until final approval.
Do not use `APP_FEATURE_FLAG=INTERNAL` in production; internal mode disables
billing and permission checks.

## Populating Canada Data

All durable Canada market facts are written to normalized relational tables in
`DATABASE_MARKET_URL`. The Canada pipeline must not persist market payloads in
JSON files or JSON database columns.

### Path A: Official SEC Filings

This path is suitable only for Canadian issuers that have an SEC identity and
at least three aligned annual periods in standardized 10-K, 20-F, or 40-F XBRL.

```bash
set -a
source .env
set +a

PYTHONPATH=. python -m codes.workers.canada_ingest_worker \
  --symbol SHOP.TO
```

If the Canadian and SEC symbols differ, provide the verified SEC ticker:

```bash
PYTHONPATH=. python -m codes.workers.canada_ingest_worker \
  --symbol ABX.TO \
  --sec-ticker B
```

The worker checks Canadian EDGAR identity before importing CompanyFacts. It
detects IFRS or US-GAAP, CAD or USD reporting currency, aligned annual periods,
filing provenance, balance reconciliation, and dated shares. Failed validation
writes no public screener row.

This command does not populate the full Canadian market. It must never be used
as evidence that TSX or TSXV support is complete.

### Path B: Verified Licensed-Source Exports

The backward-compatible CSV importer accepts structured exports produced under
a licence that permits this product's storage and use. It does not download or
scrape SEDAR+.

```bash
BUNDLE_DIR=/absolute/path/to/verified/SHOP.TO

PYTHONPATH=. python -m codes.workers.canada_ingest_worker \
  --symbol SHOP.TO \
  --company-csv "$BUNDLE_DIR/company.csv" \
  --periods-csv "$BUNDLE_DIR/periods.csv" \
  --documents-csv "$BUNDLE_DIR/documents.csv" \
  --facts-csv "$BUNDLE_DIR/facts.csv" \
  --shares-csv "$BUNDLE_DIR/shares.csv"
```

Required schemas and confidence values are documented in
`docs/track_b_canada.md`. Do not create placeholder financial records to make a
bundle pass. Source documents, identifiers, dates, currencies, shares, and
fact-level provenance must come from the licensed or issuer-verified source.

### Full-Market Population

There is intentionally no full-market population command yet. Before one is
implemented:

1. Execute the source and redistribution agreements.
2. Obtain the licensed delivery specification and test feed.
3. Build a licensed-feed adapter into the canonical provider layer.
4. Add issuer identity, dual-list, restatement, amendment, and corporate-action
   handling.
5. Load a staging database first.
6. Produce the coverage and audit reports described below.
7. Obtain written release approval before loading the public production view.

Public SEDAR+ web pages must not be scraped to fill this gap.

## Database Verification

Run these checks after every staging or production import:

```bash
psql "$DATABASE_MARKET_URL" -v ON_ERROR_STOP=1
```

Then run:

```sql
SELECT market_code, COUNT(*) AS issuers
FROM market_issuers
GROUP BY market_code
ORDER BY market_code;

SELECT confidence, can_score, COUNT(*) AS issuers
FROM market_quality_reports
WHERE market_code = 'CA'
GROUP BY confidence, can_score
ORDER BY confidence, can_score;

SELECT symbol, COUNT(DISTINCT fiscal_year) AS fiscal_years
FROM market_statement_facts
WHERE market_code = 'CA'
GROUP BY symbol
HAVING COUNT(DISTINCT fiscal_year) < 3
ORDER BY symbol;

SELECT f.symbol, f.fact_name, f.fiscal_year, f.source_document_id
FROM market_statement_facts AS f
LEFT JOIN market_source_documents AS d
  ON d.market_code = f.market_code
 AND d.symbol = f.symbol
 AND d.document_id = f.source_document_id
WHERE f.market_code = 'CA'
  AND d.document_id IS NULL
ORDER BY f.symbol, f.fiscal_year DESC, f.fact_name;

SELECT symbol, confidence, can_score
FROM market_quality_reports
WHERE market_code = 'CA'
  AND (
    can_score IS NOT TRUE
    OR confidence NOT IN (
      'regulatory_verified',
      'issuer_verified',
      'licensed_source_verified'
    )
  )
ORDER BY symbol;

SELECT symbol, name, currency, data_confidence, projection_version, updated_at
FROM market_screener_rows
WHERE market_code = 'CA'
ORDER BY symbol;
```

The fiscal-year, missing-document, and weak-confidence queries must return no
unexpected public candidates. Review every exception; do not hide it by
weakening the query or changing confidence labels.

After database checks, verify at minimum:

- `/screener/ca` selects Canada and remains selected after refresh.
- U.S. `/screener/us` data is unchanged.
- Every displayed Canadian value shows the filing reporting currency.
- An unsupported issuer refuses to score rather than falling back to guessed or
  provider-only facts.
- Desktop and mobile layouts remain readable.

## Software and Content Licensing

Data licences do not grant permission to publish this source code, and a
software licence does not grant market-data rights. Clear both reviews
separately.

### Repository Licence Decision

There is currently no root `LICENSE` file. Before making the repository public
or distributing its code or container image:

1. Identify the legal owner of every material contribution.
2. Decide whether the code remains private/proprietary or is released under a
   named open-source licence.
3. Have counsel confirm that employee, contractor, and prior-code ownership is
   documented and compatible with that decision.
4. Add the exact counsel-approved `LICENSE`, copyright notice, and distribution
   terms. Do not select a licence merely because a hosting site suggests one.
5. Keep the repository private until this gate is signed.

### Dependency and Asset Audit

Run the audit in a clean virtual environment built from the production
requirements:

```bash
python3 -m venv /tmp/graham-release-audit-venv
source /tmp/graham-release-audit-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pip-audit pip-licenses

pip-audit -r requirements.txt --strict
pip-licenses \
  --format=plain-vertical \
  --with-urls \
  --with-license-file \
  --no-license-path

find assets -type f -print | sort
deactivate
```

The tools provide an inventory; they do not give legal approval. For every
direct and transitive package, font, image, icon, dataset, copied snippet, and
model artifact:

- record its exact version, source, copyright owner, licence text, and intended
  production/distribution use;
- resolve `UNKNOWN`, ambiguous, custom, copyleft, source-available, or
  dual-licensed results with counsel;
- satisfy attribution, notice, source-offer, modification, and redistribution
  duties; and
- create a reviewed `THIRD_PARTY_NOTICES` file before publication.

For `assets/logo.png`, retain the original design agreement or other written
ownership evidence. Replace it before release if commercial rights cannot be
proved.

Send the dependency output, asset inventory, proposed repository licence, and
distribution architecture to the Canadian legal-review contact in the email
template below. Ask counsel to approve both hosted SaaS use and any source,
container, desktop, or customer deployment that may be distributed.

## Canada Data Rights

This section is an operational checklist, not legal advice. The signed
agreements and advice from qualified Canadian counsel control.

### SEDAR+

The public SEDAR+ Terms of Use prohibit automated scraping, constructing a
database from public-site content, and commercializing or mass-distributing that
content. Do not build or run a public-site scraper.

Official references:

- [SEDAR+ Terms of Use](https://systems.securities-administrators.ca/terms-of-use/)
- [SEDAR+ Data Distribution Service FAQ](https://systems.securities-administrators.ca/onlinehelp/faqs/general-faqs-about-filings/)
- [CSA Service Desk contact](https://systems.securities-administrators.ca/contact-us/)

Contact the CSA Service Desk about the SEDAR+ Data Distribution Service:

- Email: `sedarplus@csa-acvm.ca`
- North America: `1-800-219-5381`
- Outside North America: `1-514-878-8377`

Technical access or an email conversation is not a licence. Do not release until
an executed agreement grants the required commercial access, normalization,
storage, historical retention, derived-data, display, and redistribution rights.

### TSX and TSXV

Contact TMX Datalinx for issuer/security reference data, symbol status, corporate
actions, and any delayed, end-of-day, or real-time market data required by the
product:

- Email: `marketdata@tmx.com`
- [TMX Datalinx contact page](https://www.tmxinfoservices.com/contact-us)
- [TMX pricing and contract documents](https://www.tmxinfoservices.com/market-data/pricing-and-contract-documents)

Ask whether the application is an end user, vendor, distributor, or derived-data
service under TMX's definitions. Do not assume that buying a data subscription
permits display to paid users or redistribution outside Canada.

### SEC EDGAR

The SEC states that public EDGAR filing content is free to access and reuse, but
automated clients must declare a user agent and remain within fair-access limits.
This does not provide TSX/TSXV market-data rights or complete Canadian coverage.

- [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
- [SEC Developer Resources](https://www.sec.gov/about/developer-resources)

Use a monitored production identity in `SEC_USER_AGENT`. For access-denied or
undeclared-bot problems, the SEC webmaster FAQ identifies
`webmaster@sec.gov`; it is not a licensing or implementation support channel.

### Commercial Providers

FMP or any other normalized provider is not an approved public Canada source by
default. Before using one, obtain a contract that explicitly covers:

- Commercial use in this product and all intended countries.
- Storage and retention of normalized and historical records.
- Display and redistribution to free, paid, and institutional users.
- Derived scores, rankings, alerts, exports, and API use, if applicable.
- Source-document identifiers and per-fact provenance.
- Restatements, corrections, delistings, and corporate actions.
- Audit obligations, usage reporting, attribution, deletion, and termination.

Provider access without these rights remains internal-only.

## Licensing Email Templates

Replace every bracketed field. Send from the legal entity that will sign the
agreement. Save replies and executed contracts in a private contract system,
not in this repository.

### CSA / SEDAR+ Data Distribution Service

To: `sedarplus@csa-acvm.ca`

Subject: `Commercial SEDAR+ Data Distribution Service licensing inquiry`

```text
Hello CSA Service Desk,

I am contacting you on behalf of [legal company name], operator of
[product name and domain]. We are evaluating Canadian public-company coverage
for a web-based equity research product. Canada has no announced launch date,
and we will not launch or ingest from the SEDAR+ public website.

We would like information about the SEDAR+ Data Distribution Service and the
agreement required for this use case:

- automated receipt of public issuer filings and metadata;
- normalization into a private relational database;
- retention of current, historical, amended, and restated facts;
- calculation of derived financial metrics, scores, rankings, and warnings;
- display of selected facts, derived outputs, source identifiers, and links to
  users in [countries];
- access by [free, paid, professional, and/or institutional] users; and
- production, staging, backup, disaster-recovery, and audit copies.

Please identify:

1. the correct service, technical specification, test access, and agreement;
2. commercial storage, derived-data, display, and redistribution rights;
3. geographic, user-type, attribution, retention, deletion, and audit limits;
4. pricing, minimum term, reporting obligations, and implementation lead time;
5. treatment of personal information that may appear in filings; and
6. the contact authorized to confirm these rights in the executed agreement.

Our anticipated architecture is:
SEDAR+ licensed delivery -> Canada adapter -> canonical financial facts ->
validation and provenance -> derived research views.

Please let us know what additional information you require.

Regards,
[name]
[title]
[legal company]
[address]
[phone]
[monitored email]
```

### TMX Datalinx

To: `marketdata@tmx.com`

Subject: `TSX/TSXV reference and market data licensing inquiry`

```text
Hello TMX Datalinx,

I am contacting you on behalf of [legal company name], operator of
[product name and domain]. We are evaluating Canadian equity coverage for a
web-based research product. Canada has no announced launch date and will remain
disabled until the required agreements are executed.

We need guidance on licensing for:

- the current and historical TSX/TSXV issuer and security master;
- symbol changes, listing status, delistings, and corporate actions;
- [delayed/end-of-day/real-time] prices, volume, and market capitalization;
- storage in production, staging, backup, and disaster-recovery systems;
- display to [free, paid, professional, and/or institutional] users in
  [countries]; and
- derived valuations, scores, rankings, alerts, charts, and portfolio analytics.

Please confirm:

1. whether our use is classified as end-user, vendor, distributor, or derived
   data;
2. the required products, agreements, exhibits, and technical delivery method;
3. display, non-display, derived-data, storage, historical-retention, and
   redistribution rights;
4. user classification, entitlement, attribution, reporting, and audit duties;
5. pricing, minimum term, implementation lead time, and termination/deletion
   obligations; and
6. whether separate agreements are required for TSX, TSXV, indices, and users
   outside Canada.

Please send the applicable product sheets, price schedules, sample agreement,
and next steps.

Regards,
[name]
[title]
[legal company]
[address]
[phone]
[monitored email]
```

### Canadian Legal Review

To: `[Canadian securities, data-licensing, privacy, and technology counsel]`

Subject: `Pre-launch legal review for Canadian equity research coverage`

```text
Hello [counsel name],

[Legal company] is considering adding Canadian public-company research to
[product/domain]. There is no announced launch date. The feature is disabled
and will remain disabled pending written approval.

Please review:

- the proposed SEDAR+ and TMX agreements and our intended technical use;
- storage, normalization, derived-data, display, redistribution, backup,
  retention, deletion, attribution, and audit obligations;
- use of SEC filings for Canadian cross-listed issuers;
- privacy implications of filing content and product analytics;
- Terms of Service, Privacy Policy, financial-advice disclaimers, source labels,
  confidence labels, marketing claims, and subscription copy;
- availability of scores and portfolio analytics to retail, professional, and
  institutional users in Canada and other countries; and
- any required registrations, restrictions, insurance, or risk disclosures.

Please provide a written go/no-go memorandum, a list of required changes, and
confirmation of which executed agreements must be in place before release.

Attached/linked:
- architecture and data-flow diagram;
- field-level data inventory and retention schedule;
- draft customer-facing screens and copy;
- proposed source contracts;
- coverage and manual-audit reports; and
- incident, correction, and takedown procedures.

Regards,
[name]
[title]
[legal company]
```

## Canada Public Release Gates

Every checkbox is blocking. An unknown answer is a failed gate.

### Legal and Licensing

- [ ] The legal company and product/domain are finalized.
- [ ] A SEDAR+ DDS or equivalent full-fundamentals agreement is executed.
- [ ] The agreement expressly permits every planned storage, derived-data,
      display, paid-user, institutional-user, geographic, backup, and retention
      use.
- [ ] Required TMX or licensed-vendor agreements are executed for issuer master,
      symbols, corporate actions, and prices.
- [ ] Attribution, audit, reporting, deletion, renewal, and termination duties
      are implemented and assigned to an owner.
- [ ] Canadian counsel has delivered a written go/no-go review.
- [ ] Terms, privacy, disclaimers, subscription copy, source labels, and
      marketing claims have counsel approval.
- [ ] Source terms, product names, pricing, and contacts have been reverified
      against official pages during the final release review.
- [ ] No contract or credential is stored in git.

### Software and Content

- [ ] The repository distribution model is approved in writing.
- [ ] A counsel-approved root `LICENSE` exists before any public source release.
- [ ] Every contributor's ownership or assignment is documented.
- [ ] Direct and transitive dependencies have an approved licence inventory.
- [ ] `THIRD_PARTY_NOTICES` contains every required notice and attribution.
- [ ] Commercial rights to the logo and every other bundled asset are recorded.
- [ ] No copied code, image, font, dataset, model, or document has unknown
      provenance or incompatible terms.

### Data Quality and Coverage

- [ ] At least 50 large/liquid issuers pass validation.
- [ ] At least three aligned fiscal years exist per issuer where available.
- [ ] Every core fact has source-document, filing-date, period, currency,
      accounting-standard, extraction, normalization, and confidence evidence.
- [ ] Shares are dated and sourced.
- [ ] Assets reconcile to liabilities plus equity within approved tolerance.
- [ ] Amendments and restatements are detected and tested.
- [ ] Dual-listed issuers map to one identity without ticker collisions.
- [ ] TSX and TSXV listing types, classes, funds, trusts, banks, insurers, and
      unsupported issuer types are explicitly documented.
- [ ] Delisted issuers and survivorship-bias limitations are documented.
- [ ] A manual audit sample has been compared with the actual filings.
- [ ] Coverage, pass-rate, refusal-rate, staleness, and source-outage reports are
      reviewed and approved.
- [ ] Provider-normalized internal-only facts cannot enter a public score.
- [ ] No required market dataset is persisted as an unlicensed JSON payload.

### Product Parity

- [ ] Canada screener, company analysis, historical analysis, portfolio, risk,
      benchmark, simulation, and export workflows have explicit support or an
      honest no-score state.
- [ ] Clicking a Canadian issuer does not route through a U.S.-only data path.
- [ ] Original reporting currency and any display conversion are clearly
      distinguished.
- [ ] FX conversion never changes score calculations, portfolio weights, or
      risk calculations.
- [ ] Price, momentum, benchmark, market-cap, and fair-value displays use
      licensed and correctly mapped listing data.
- [ ] Users can see source and confidence information for material outputs.
- [ ] Product copy does not imply SEC, CSA, SEDAR+, or TMX endorsement.
- [ ] Desktop and mobile workflows pass browser and accessibility testing.
- [ ] Free, paid, professional, and institutional entitlements match contracts.

### Engineering and Operations

- [ ] The complete test suite passes with zero unexpected failures.
- [ ] Full tests run in CI for every Canada change; security-only CI is not
      sufficient.
- [ ] Database migrations run successfully on an empty database and a production
      snapshot.
- [ ] Existing verified facts backfill new projections without user reanalysis.
- [ ] Import reruns are idempotent and failed imports remove stale public rows.
- [ ] Staging load, production load, rollback, and licence-termination deletion
      procedures are tested.
- [ ] Encrypted backups run on schedule.
- [ ] `scripts/restore_test.sh` is corrected and a real restore drill passes.
- [ ] Refresh scheduling, stale-data alerts, source failures, corrections,
      restatements, and incident response have owners and monitoring.
- [ ] Load, latency, database pool, and rate-limit tests pass at expected traffic.
- [ ] `SEC_USER_AGENT` identifies the production company and monitored contact.
- [ ] Production uses HTTPS, managed authentication, Redis, secret management,
      secure cookies, and separate market/user databases.

### Approval

- [ ] Legal owner signs go-live approval.
- [ ] Data owner signs coverage and audit approval.
- [ ] Engineering owner signs deployment and rollback approval.
- [ ] Product owner signs user-copy and entitlement approval.
- [ ] Operations owner signs monitoring, renewal, and incident approval.
- [ ] The approval record links the exact contract versions, commit, database
      snapshot, audit report, and release candidate.

Only after every checkbox is complete may a release commit change `CA` to
`true`.

## Approved Release Procedure

Use this procedure only after the approval gate is complete:

1. Record the approved commit and contract versions in the private release
   dossier.
2. Back up all production databases and complete a restore drill.
3. Load the licensed source into staging.
4. Run the SQL checks, complete test suite, audit sample, and browser smoke
   tests.
5. Load production through the same versioned worker and verify row counts.
6. Change `CA` from `false` to `true` in one dedicated release commit.
7. Confirm the production tier is not `INTERNAL` or `BETA`.
8. Deploy and test `/screener/us`, `/screener/ca`, Canadian analysis, portfolio,
   authentication, billing, privacy, and source displays.
9. Monitor ingestion, error, latency, and user-support channels.
10. Keep the rollback owner available during the release window.

Emergency visibility rollback:

1. Set `CA` to `false` in `feature_flags.json`.
2. Deploy immediately.
3. Preserve evidence and investigate before re-enabling.
4. Do not delete licensed data unless the agreement, counsel, or incident plan
   requires deletion. If deletion is required, follow the approved procedure and
   preserve the legally permitted audit record.

## General Publication Gate

Canada approval does not replace the application's general launch work. Before
any public production release:

While Canada remains unapproved, run this exact fail-closed tier and market
check in the release shell after loading production environment variables:

```bash
PYTHONPATH=. python -c \
  'from codes.core.app_flags import get_current_flag, is_market_enabled; tier = get_current_flag(); assert tier not in {"INTERNAL", "BETA"}, f"unsafe public tier: {tier}"; assert not is_market_enabled("CA"), "Canada is not approved"; print(f"public_preflight=ok tier={tier} canada=false")'
```

This command is expected to fail on the current development branch because its
tier is `INTERNAL`. Do not bypass the assertion; configure an approved public
tier and keep Canada disabled.

- Require zero unexpected failures from `PYTHONPATH=. pytest -q`.
- Require passing dependency and security scans.
- Complete the repository, dependency, and asset licensing review above.
- Configure production authentication, HTTPS, secure cookies, CSRF controls,
  Redis-backed rate limits, and secret rotation.
- Validate Stripe products, webhooks, entitlements, trials, refunds, and
  cancellation behavior if billing is enabled.
- Review `/terms`, `/privacy`, disclaimers, analytics consent, and retention with
  counsel.
- Test encrypted backups and restoration using the actual database schemas.
- Configure error monitoring, uptime checks, analytics privacy controls, alert
  routing, and an incident-response owner.
- Verify that production does not run with `APP_FEATURE_FLAG=INTERNAL`.
- Complete every blocking item in `Publish.md` and `SECURITY_CHECKLIST.md`.

## Decision Rule

No signed right, no source. No provenance, no score. No complete gate, no
Canada release.

Do not treat any of the following as approval:

- a working endpoint;
- public browser access;
- a vendor sales demonstration;
- a quote or invoice;
- a verbal statement;
- an email that is not incorporated into the executed agreement;
- internal quality status;
- a feature flag;
- a passing test subset; or
- pressure to announce a launch date.
