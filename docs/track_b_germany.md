# Track B Germany Notes

Branch: `germany`

Status: internal validation only. There is no Germany launch date. The committed
`DE` market flag is disabled.

## Scope

Germany uses the shared relational `market_*` PostgreSQL tables keyed by `DE`.
It does not create a country database, country table family, JSON files, or JSON
payload storage. The provider adapter shields the main analysis engine from
Germany-specific sources and emits canonical facts before the legacy scoring
bridge is used.

The canonical screener route is `/screener/de`; `/screener/germany` and
`/screener/deutschland` are aliases. Routing only selects a market. It cannot
bypass validation, provenance, or release gates.

## Sources And Limits

Approved imports must be structured exports from BaFin, Bundesanzeiger,
Unternehmensregister, issuer annual reports, Deutsche Boerse metadata, or a
licensed source with documented commercial rights and source provenance. The
web app and worker do not scrape public pages.

German statements are accepted only through deterministic mappings recorded in
`germany_normalization.py`. The bridge explicitly supports IFRS, EU-adopted
IFRS, and HGB. Unknown German labels, accounting mappings, exchanges, security
types, currencies, document references, or balance-sheet reconciliation fail
closed rather than being inferred.

ADRs and investment trusts are stored but cannot receive the ordinary-share
scoring model. Price-based calculations remain unavailable until a licensed
price feed supplies explicit currency, quote unit, corporate-action adjustment,
timestamp, and redistribution rights.

## Local Validation

Initialize the regular market database:

```bash
set -a
source .env
set +a
PYTHONPATH=. python -c 'from codes.data import db; db.init_db(); print("market_schema_ready=true")'
```

For local validation only, set `DE` to `true` in `feature_flags.json`, restart
the app, and open `/screener/de`. Before commit or deployment, restore `DE` to
`false`.

## Verified Bundle And Import

Each issuer directory requires:

- `company.csv`: `symbol,name,exchange,country,currency,regulator_id,security_type,accounting_standard`
- `periods.csv`: `symbol,fiscal_year,fiscal_period,period_end,currency`
- `documents.csv`: `document_id,source,url,filing_date,period_end,form,confidence`
- `facts.csv`: `symbol,statement_type,fact_name,fiscal_year,fiscal_period,period_end,currency,value,source_document_id,source_url,confidence,accounting_standard,extraction_method,normalization_method`
- `shares.csv`: `symbol,shares_outstanding,as_of,source`

`lei` or `register_number` may replace `regulator_id`. Public confidence values
are `regulatory_verified`, `issuer_verified`, `licensed_source_verified`, and
`cross_checked`. `provider_normalized_internal_only` requires `--allow-internal`
and never produces a public screener projection.

```bash
PYTHONPATH=. python -m codes.workers.germany_ingest_worker \
  --symbol SAP.DE \
  --bundle-dir /absolute/path/to/verified/SAP.DE
```

The worker checks every required path before importing, validates the full
bundle, then writes canonical facts, provenance, quality results, and an
eligible screener projection atomically.

## Public Release Gates

Germany remains disabled until written evidence confirms:

- Commercial reuse, display, storage, derived-data, retention, and audit terms
  for every production data source.
- A production acquisition/extraction job with identity mapping, amendment and
  restatement handling, source retention, monitoring, and retry controls.
- A source-audited 50-issuer minimum universe with three annual periods where
  available and tested IFRS/HGB German-label mappings.
- A licensed Germany quote and corporate-action source before price-based
  outputs are displayed.
- Coverage, error-rate, desktop/mobile behavior, backup/restore, and written
  Legal, Data, Engineering, Product, Security, and Operations sign-off.
