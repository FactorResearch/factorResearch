# Track B United Kingdom Runbook

Branch: `uk`

Status: internal validation only. There is no UK launch date. The committed
public-safe default is `"GB": false`.

## Architecture

The UK uses the same provider-neutral boundary as Canada while remaining an
independent feature:

```text
verified UK source export
  -> UK adapter and validation
  -> canonical relational market facts (`market_code = 'GB'`)
  -> versioned screener projection and analysis models
```

The source payload is never stored as a JSON file. Durable issuer facts use
`market_issuers`, `market_fiscal_periods`, `market_statement_facts`,
`market_source_documents`, `market_shares_outstanding`,
`market_quality_reports`, `market_quality_issues`, and
`market_screener_rows` in `DATABASE_MARKET_URL`. User data remains in
`DATABASE_USERS_URL`.

One shared market database keyed by ISO market code is the default. Split the
UK into a separate physical database only if a contract, data-residency rule,
or measured scaling need requires it.

## Sources and Boundaries

Accepted evidence can originate from:

- Companies House company identity, filing history, and filed accounts;
- FCA National Storage Mechanism annual financial reports and iXBRL exports;
- issuer-hosted annual reports; or
- a licensed source whose contract permits storage, derived analysis, and
  display to the application's user tiers.

Companies House identity alone is not proof of an LSE listing. The production
pipeline needs an approved ticker-to-company-number/LEI mapping. FCA filing
availability does not grant LSE symbol, corporate-action, or price rights.

Do not scrape Companies House, FCA, issuer, or LSE web pages. Build an approved
API, bulk-data, licensed-feed, or controlled issuer-document acquisition job
after its terms are recorded.

Official references:

- Companies House developer hub: https://developer.company-information.service.gov.uk/
- Companies House filing-history API: https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/reference/filing-history
- FCA National Storage Mechanism: https://www.fca.org.uk/markets/primary-markets/regulatory-disclosures/national-storage-mechanism
- FCA NSM terms: https://data.fca.org.uk/artefacts/NSM_Terms_of_Use.pdf
- LSE market-data pricing and policies: https://www.londonstockexchange.com/securities-trading/market-data/pricing-and-policies

Terms and pricing change. Recheck the official documents immediately before
contracting or approving release.

## Local Enablement

Initialize the normal market database first:

```bash
set -a
source .env
set +a

PYTHONPATH=. python -c \
  'from codes.data import db; db.init_db(); print("market_schema_ready=true")'
```

For local validation only, set `GB` to `true` in `feature_flags.json`, restart
the app, and open `/screener/gb`. Keep `CA` independent; either country can be
enabled or disabled without changing the other.

Before committing or deploying, restore `"GB": false` and verify:

```bash
PYTHONPATH=. python -c \
  'from codes.core.app_flags import is_market_enabled; assert not is_market_enabled("GB"); print("uk_disabled=true")'
```

## Verified Bundle

Each issuer directory must contain:

- `company.csv`: `symbol,name,exchange,country,currency,regulator_id,security_type,accounting_standard`
- `periods.csv`: `symbol,fiscal_year,fiscal_period,period_end,currency`
- `documents.csv`: `document_id,source,url,filing_date,period_end,form,confidence`
- `facts.csv`: `symbol,statement_type,fact_name,fiscal_year,fiscal_period,period_end,currency,value,source_document_id,source_url,confidence,accounting_standard,extraction_method,normalization_method`
- `shares.csv`: `symbol,shares_outstanding,as_of,source`

`company_number` or `lei` may replace `regulator_id`. Supported security types
are `ordinary_share`, `adr`, and `investment_trust`. Only `ordinary_share` can
currently score. Supported statement types are `income`, `balance`, and
`cash_flow`.

Public confidence values are `regulatory_verified`, `issuer_verified`,
`licensed_source_verified`, and `cross_checked`. The value
`provider_normalized_internal_only` requires `--allow-internal` and never
creates a public screener projection.

Every required fact needs an accepted accounting standard: `IFRS`,
`UK-adopted IFRS`, `UK GAAP`, `FRS 101`, or `FRS 102`. Do not label an unknown
mapping merely to pass validation. Public scoring also requires at least three
distinct aligned annual periods for every required fact.

## Import

```bash
PYTHONPATH=. python -m codes.workers.uk_ingest_worker \
  --symbol VOD.L \
  --bundle-dir /absolute/path/to/verified/VOD.L
```

Explicit paths remain available:

```bash
PYTHONPATH=. python -m codes.workers.uk_ingest_worker \
  --symbol VOD.L \
  --company-csv /path/company.csv \
  --periods-csv /path/periods.csv \
  --documents-csv /path/documents.csv \
  --facts-csv /path/facts.csv \
  --shares-csv /path/shares.csv
```

The worker checks all paths before import and reports every missing file. It
normalizes `VOD:LSE` and `VOD.LSE` to `VOD.L`, validates identity, security
type, source authority, fact provenance, accounting standards, reporting
currency, dated shares, and balance reconciliation, then writes the canonical
facts and eligible screener projection atomically.

The repository intentionally contains no fabricated issuer bundle. Source
exports must be created by the approved acquisition process.

## Database Checks

```sql
SELECT symbol, name, exchange, regulator_id, security_type,
       accounting_standard, currency
FROM market_issuers
WHERE market_code = 'GB'
ORDER BY symbol;

SELECT confidence, can_score, COUNT(*)
FROM market_quality_reports
WHERE market_code = 'GB'
GROUP BY confidence, can_score;

SELECT symbol, COUNT(DISTINCT fiscal_year) AS fiscal_years
FROM market_statement_facts
WHERE market_code = 'GB'
GROUP BY symbol
HAVING COUNT(DISTINCT fiscal_year) < 3;

SELECT f.symbol, f.fact_name, f.fiscal_year
FROM market_statement_facts AS f
LEFT JOIN market_source_documents AS d
  ON d.market_code = f.market_code
 AND d.symbol = f.symbol
 AND d.document_id = f.source_document_id
WHERE f.market_code = 'GB' AND d.document_id IS NULL;

SELECT symbol, currency, data_confidence, projection_version, updated_at
FROM market_screener_rows
WHERE market_code = 'GB'
ORDER BY symbol;
```

## Price and Currency Safety

Financial-statement values remain in the issuer's reported currency; GBP is
not forced. Mixed reporting currencies across scoring periods are rejected.

London market quotes may be denominated in GBP or GBX. The branch therefore
does not request or apply a live UK price. Price-based Graham value, market cap,
momentum, and related outputs stay unavailable until a licensed price record
includes exchange, timestamp, ISO currency, quote unit, adjustment status, and
corporate-action provenance. Never infer GBX from ticker suffix alone.

## Licensing Inquiry Template

Use the LSE market-data portal/contact route linked above. Record the sent
message and response in the private release dossier.

Subject: `Commercial LSE data licensing for equity research application`

```text
Hello,

We operate a commercial web-based equity research application and are
evaluating United Kingdom coverage. We need written terms and pricing for LSE
and AIM issuer/reference data, symbol status, corporate actions, and delayed or
end-of-day prices.

The application stores normalized records in our backend, displays source and
derived analytics to free, paid, professional, and institutional users, and may
serve users inside and outside the United Kingdom. Please confirm the licences,
reporting obligations, attribution, audit rights, retention/caching rules,
derived-data rights, user/device fees, geographic limits, and deletion duties
that apply.

No UK market is publicly enabled while this review is open.

Regards,
[Name]
[Company]
[Contact details]
```

Send a separate written description of the intended commercial storage,
normalization, display, and derived-analysis use to Companies House/FCA through
their current official support routes and ask for confirmation of applicable
terms. Do not rely on an informal assumption that public access equals
commercial redistribution permission.

## Public Release Gates

UK remains disabled until all items have written evidence:

- Approved Companies House/FCA/issuer/licensed-source commercial-use terms.
- Executed LSE agreements for required issuer, reference, corporate-action,
  and market data, including all user tiers and territories.
- Approved ticker, ISIN/LEI, and Companies House identity master with duplicate,
  renamed, delisted, and cross-listed controls.
- Production acquisition and extraction job with retries, rate limits,
  amendment/restatement handling, source retention rules, and monitoring.
- Audited IFRS/UK GAAP mappings across the target universe.
- Separate product behavior for ordinary shares, ADRs, and investment trusts.
- Licensed GBP/GBX-aware prices and corporate-action adjustments before any
  price-based score is shown.
- Coverage report, manual source-to-output audit, failure-rate thresholds, and
  documented no-score behavior approved by Data and Product.
- Desktop and mobile verification of routing, empty states, source labels,
  currencies, stale data, and errors.
- Full automated test suite and backup/restore test passing in production-like
  infrastructure.
- Written Legal, Data, Engineering, Product, Security, and Operations sign-off.

Passing one issuer import or enabling `GB` locally is not release approval.
