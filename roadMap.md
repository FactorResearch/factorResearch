# Factor Research --- Master Technical Roadmap (AI Implementation)

> Status: Approved
>
> This document defines the long-term technical architecture for Factor
> Research.
>
> **Primary objective**
>
> Build the platform architecture first. Release features only when they
> are mature.
>
> Every component must be:
>
> -   Modular
> -   Provider agnostic
> -   Independently testable
> -   Feature-flagged
> -   Versioned
> -   Reusable across Website, API, Desktop and Mobile.

------------------------------------------------------------------------

# V0.5 --- Architecture Freeze

Goal

Finalize the internal architecture before public launch.

This phase is **not user-facing**.

## Engineering Rules

-   Never call vendor APIs from business logic.
-   All calculations operate on normalized models.
-   Every engine must expose:
    -   Input schema
    -   Output schema
    -   Validation
    -   Unit tests
    -   Documentation
    -   Interpretation guide
-   Engines must support feature flags:
    -   internal
    -   beta
    -   v1
    -   v2
    -   enterprise
-   Shared mathematical library:
    -   CAGR
    -   Volatility
    -   Sharpe
    -   Sortino
    -   Calmar
    -   Alpha
    -   Beta
    -   Correlation
    -   Covariance
    -   Regression
    -   Drawdown
    -   Percentile normalization
    -   Winsorization
    -   Ranking

Architecture

UI ↓ Analysis Engines ↓ Canonical Financial Models ↓ Provider Adapters ↓
FMP / SEC / Future Providers

------------------------------------------------------------------------

# V1 --- Launch

Data Providers

-   FMP
-   SEC EDGAR
-   PostgreSQL

Includes

-   Company analysis
-   Portfolio analysis
-   Screener
-   Historical analyses
-   User portfolios
-   Formula Lab (basic)
-   Backtesting
-   Premium subscriptions
-   SEO company pages

------------------------------------------------------------------------

# Track A --- Quant Research

## V2.0 Portfolio Optimization [x]

-   Mean-Variance Optimizer
-   Maximum Sharpe
-   Minimum Variance
-   Risk Parity
-   Later improvement: use SciPy linear algebra / covariance repair in
    portfolio simulation when covariance matrices are near-singular or not
    positive semidefinite.

## V2.1 Risk Analytics [x]

-   Ohlson O-Score
-   Zmijewski Score
-   Altman integration
-   Maximum Drawdown
-   Portfolio maximum drawdown
-   Portfolio downside deviation
-   VaR
-   CVaR
-   Recovery time
-   Drawdown curve
-   Underwater chart
-   Worst month/quarter/year
-   Recovery Factor
-   Ulcer Index
-   Rolling Sharpe
-   Rolling Sortino

## V2.2 Factor Research [x]

-   CAPM
-   Fama-French 3 Factor
-   Fama-French 5 Factor
-   Carhart Four Factor
-   Holdings attribution
-   Return attribution
-   Rolling attribution

## V2.3 Accounting Intelligence [x]

Goal

Build a dedicated accounting and forensic-analysis layer that makes
statement-quality risk obvious without forcing users to inspect many small
cards.

This version should consolidate accounting diagnostics into one coherent
section designed to expand over time.

Core engine

-   Accounting Quality Engine
-   Accounting Quality Score
-   Accounting Grade
-   Accounting Risk Level
-   Manipulation Risk
-   Plain-English explanation
-   Individual warning flags

Version 2.3.1

-   Beneish M-Score
-   Manipulation Risk

Version 2.3.2

-   Dechow F-Score
-   Advanced Fraud Dashboard

Layout / UX requirements

-   The analysis page must have a dedicated `Accounting` section.
-   Accounting models must be grouped into a scalable section, not scattered
    as many peer-level cards.
-   The section must be designed to support future forensic engines without a
    page redesign.
-   Desktop, tablet and mobile layouts must all preserve clear accounting
    hierarchy.
-   Light mode and dark mode must both be first-class, not dark-first with a
    weak light fallback.

Data / architecture requirements

-   Reuse outputs from Piotroski, FCF Quality, Growth Quality and related
    engines where appropriate instead of duplicating logic.
-   Every new accounting model must support cached-analysis backfill for
    already analyzed stocks in Postgres.
-   Users must not need to rerun manual analysis to receive newly added
    accounting diagnostics on existing cached analyses.

## V3 Institutional Portfolio Analytics [x]

-   Sector exposure
-   Industry exposure
-   Country exposure
-   Market-cap exposure
-   Style exposure
-   Estimated liquidity
-   Hidden concentration detection
-   Correlation matrix
-   Hierarchical clustering
-   PCA
-   Monte Carlo ( we want to have the current basic carlo for basic clients and save this advance one for higher tier, make sure to code it in a way to make that possible)
    -   GBM
    -   Bootstrap
    -   Fat-tail
    -   Regime-aware
-   Historical stress testing

------------------------------------------------------------------------

# Track B --- Global Market Engine

Goal

Support non-U.S. equity markets through one unified analysis engine without
lowering trust, accuracy or auditability.

Brand rule

International markets must not be released as marketing checkboxes. If a
market cannot meet the same evidence standard expected from U.S. SEC-backed
analysis, it remains internal-only. Users rely on this platform for decisions
involving real money; weak, guessed or opaque data is not acceptable.

The analysis engine must never know where a company is listed.

Architecture

Regulator / issuer documents / licensed source
↓
Market-specific provider adapter
↓
Canonical financial model
↓
Validation, provenance and confidence layer
↓
Legacy scoring-input bridge
↓
Analysis engines

Market data storage

-   Use one physical `factorresearch_market` PostgreSQL database for market
    data and keep user/account data in the separate users database.
-   Store canonical international data in shared relational `market_*` tables
    keyed by `market_code`; do not create one database or one table family per
    country and do not persist market payloads as JSON files.
-   Store public screener projections in typed relational columns and create
    them in the same transaction as a quality-approved canonical import.
-   On deployment, migrate legacy country tables idempotently and backfill
    missing or version-stale projections from verified facts. Users must not
    rerun analyses to receive a new market feature.
-   PostgreSQL partitioning by `market_code` is the first scale-out option.
    Split a country into its own physical database only for licensing
    isolation, data-residency obligations, or demonstrated production load.
-   Provider adapters and market-keyed repository APIs must hide physical
    placement so a later database split does not change analysis engines or UI
    callbacks.

Market discovery and routing

-   `codes/app_modules/screener_markets.py` is the UI market registry.
-   Every market has one stable ISO-style code, URL slug, display label, flag,
    row aliases and canonical `/screener/<slug>` route.
-   The route is the screener's source of truth. Market selection must not be
    stored in callback globals, browser session state or per-market callbacks.
-   Refresh, browser history, bookmarks and shared links must preserve the
    selected market.
-   The registry controls discovery only. A market appears only when its
    `feature_flags.json` market gate is enabled; routing must never bypass the
    provider, provenance, validation or release gates below.
-   Adding a market must extend the registry and feature flag, not duplicate
    screener callbacks. For example, the United Kingdom uses `GB` and
    `/screener/gb`; France uses `FR` and `/screener/fr`.

Important

Do not force foreign markets to pretend they are SEC data. The canonical model
is the source of truth. A SEC-style dictionary can exist only as a compatibility
bridge for existing engines.

Folder Structure

codes/data/providers/

-   sec.py
-   canada.py
-   uk.py
-   germany.py
-   france.py
-   netherlands.py
-   australia.py
-   switzerland.py
-   japan.py
-   south_korea.py
-   hong_kong.py
-   singapore.py

Every provider implements

-   get_company()
-   get_financials()
-   get_filings()
-   get_shares()
-   get_currency()
-   get_listing_information()
-   get_source_documents()
-   get_statement_provenance()

Normalization Layer

Every provider returns the same canonical objects:

-   CompanyFinancials
-   IncomeStatement
-   BalanceSheet
-   CashFlow
-   SharesOutstanding
-   Currency
-   FiscalPeriod
-   FilingDocument
-   StatementProvenance
-   DataQualityReport

Every canonical fact must carry:

-   source market
-   regulator or issuer source
-   source URL or document identifier
-   filing date
-   fiscal period
-   accounting standard
-   reported currency
-   extraction method
-   normalization method
-   confidence status

Confidence statuses

-   regulatory_verified
-   issuer_verified
-   licensed_source_verified
-   cross_checked
-   provider_normalized_internal_only
-   insufficient_source_evidence
-   failed_validation

Public release requires regulatory_verified, issuer_verified or
licensed_source_verified for the core facts used by each score. Provider data
alone is allowed for internal development, cross-checking and coverage
analysis, but not for public scoring unless the provider contract includes
source-document provenance and redistribution rights.

Required validation before scoring

-   Assets reconcile to liabilities plus equity within tolerance.
-   Revenue, operating income, net income and cash flow tie to a known fiscal
    period.
-   Shares outstanding are dated and sourced.
-   Currency is explicit for every statement period.
-   Fiscal year, period end and filing date are not contradictory.
-   Restatements and amendments are detected or conservatively flagged.
-   Accounting standard is recorded.
-   Dual-listed tickers map to one issuer identity.
-   If required facts fail validation, the app must refuse to score instead of
    guessing.

Release gates for every market

Internal-only gate

-   Adapter exists.
-   Canonical model mapping exists.
-   Provider/regulator source risks are documented.
-   Feature flag is off by default.
-   No public UI claim of support.

Beta gate

-   At least 50 large/liquid issuers validated.
-   At least three fiscal years per issuer where available.
-   Manual audit sample completed.
-   Known unsupported issuer types documented.
-   Score refusal behavior tested.

Public gate

-   Source provenance shown or stored for every core fact.
-   Validation pass rate is measured and acceptable.
-   Coverage report exists.
-   Licensing and redistribution rights are approved.
-   Currency display is correct.
-   User-facing copy clearly states the source and confidence level.
-   No "provider_normalized_internal_only" facts are used in public scores.

## Currency Engine

Display currencies supported

-   Local
-   USD
-   CAD
-   EUR
-   GBP
-   JPY
-   AUD
-   CHF
-   HKD
-   SGD

Rules

-   Single-market portfolios default to reporting currency.
-   Mixed-currency portfolios default to the user's preferred base currency.
-   If no preference exists, normalize display values to USD.
-   Always display:
    -   Original currency
    -   Display currency
    -   FX rate
    -   Conversion date
-   Every market gets its own branch and provider file.
    Example: `canada` branch -> `codes/data/providers/canada.py`.

Important

FX conversion is display only.

It must never change:

-   Graham Score
-   Buffett Score
-   Piotroski
-   Altman
-   Portfolio weights
-   Risk calculations

### Market Release Plans

#### Canada

Branch

-   `canada`

Primary sources to investigate

-   SEDAR+
-   SEDAR+ Data Distribution Service under a commercial data licence
-   SEC EDGAR for Canadian cross-listed issuers with standardized annual XBRL
-   issuer annual/interim reports
-   TSX / TSXV listing and issuer metadata
-   licensed provider only if it includes source-document provenance

Accounting and market issues

-   IFRS reporting is common.
-   CAD reporting is common but some issuers may report in USD.
-   TSX and TSXV need separate listing handling.
-   Dual-listed issuers must map to one issuer identity.
-   SEDAR+ does not provide the same simple CompanyFacts-style API as SEC
    EDGAR.
-   Public SEDAR+ pages must not be scraped or used to construct the product
    database. Full-market automation requires the licensed distribution feed
    or a verified issuer-document pipeline.

Implemented internal acquisition

-   `python -m codes.workers.canada_ingest_worker --symbol SHOP.TO` acquires
    eligible cross-listed issuers directly from official SEC endpoints and
    writes normalized relational facts, source documents, per-period
    provenance, shares, quality results and the public-confidence projection to
    the market database without local JSON or CSV prerequisites.
-   SEC ticker identity is checked against Canadian EDGAR incorporation/address
    codes before any CompanyFacts import. Different dual-list symbols require
    an explicit `--sec-ticker`; unresolved or non-Canadian collisions are
    rejected without a database write.
-   The adapter supports IFRS and US-GAAP, detects CAD or USD reporting units,
    preserves restated annual contexts, extracts class-level shares from the
    annual iXBRL filing when CompanyFacts omits dimensional share classes, and
    refuses incomplete annual data.
-   This path expands the verified internal audit set but does not satisfy full
    TSX/TSXV coverage. Canada stays internal until at least 50 issuers, manual
    audit sampling, coverage reporting, licensed redistribution review and all
    market release gates pass.

Release standard

-   Do not publicly release Canada from provider-normalized data alone.
-   Public Canada requires source-verified fundamentals, filing provenance,
    validation checks and no-score behavior for weak data.
-   Canada must have a dedicated `README_CANADA.md` release runbook before
    any publication decision; the same requirement applies to every future
    country branch with its own country-specific README.

#### United Kingdom

Branch

-   `uk`

Primary sources to investigate

-   Companies House
-   FCA National Storage Mechanism
-   London Stock Exchange issuer metadata
-   issuer annual reports

Accounting and market issues

-   IFRS and UK GAAP may both appear.
-   GBP reporting is common, but multinational issuers may report in other
    currencies.
-   Ordinary shares, ADRs and investment trusts need separate handling.

Release standard

-   Public UK support requires Companies House/FCA/issuer-source provenance,
    not provider-only data.
-   UK must have a dedicated `README_UK.md` release runbook before any
    publication decision; the same requirement applies to every future
    country branch with its own country-specific README.

#### Germany

Branch

-   `germany`

Primary sources to investigate

-   BaFin / company register sources
-   Bundesanzeiger / Unternehmensregister
-   Deutsche Boerse issuer metadata
-   issuer annual reports

Accounting and market issues

-   IFRS and German GAAP mapping must be explicit.
-   EUR reporting is common.
-   German-language statement labels require deterministic mapping.

Release standard

-   Public Germany support requires regulator/issuer-source provenance and
    tested German-language normalization.
-   Germany must have a dedicated `README_GERMANY.md` release runbook before
    any publication decision; the same requirement applies to every future
    country branch with its own country-specific README.

#### France

Branch

-   `france`

Primary sources to investigate

-   AMF
-   Euronext Paris issuer metadata
-   issuer universal registration documents and annual reports

Accounting and market issues

-   IFRS is common for listed companies.
-   EUR reporting is common.
-   French-language filings and universal registration documents require
    deterministic mapping.

Release standard

-   Public France support requires AMF/issuer-source provenance and tested
    French-language normalization.
-   France must have a dedicated `README_FRANCE.md` release runbook before
    any publication decision; the same requirement applies to every future
    country branch with its own country-specific README.

#### Netherlands

Branch

-   `netherlands`

Primary sources to investigate

-   AFM
-   Euronext Amsterdam issuer metadata
-   issuer annual reports

Accounting and market issues

-   IFRS is common.
-   EUR reporting is common.
-   Cross-listed holding companies and international registrants need identity
    mapping.

Release standard

-   Public Netherlands support requires AFM/issuer-source provenance and
    cross-listing identity controls.

#### Australia

Branch

-   `australia`

Primary sources to investigate

-   ASX announcements
-   ASIC
-   issuer annual reports

Accounting and market issues

-   IFRS-equivalent Australian standards.
-   AUD reporting is common.
-   ASX announcements may be document-first, not structured-fact-first.

Release standard

-   Public Australia support requires ASX/ASIC/issuer-source provenance and
    document extraction validation.

#### Switzerland

Branch

-   `switzerland`

Primary sources to investigate

-   SIX issuer metadata
-   FINMA where applicable
-   issuer annual reports

Accounting and market issues

-   IFRS, Swiss GAAP FER and U.S. GAAP may appear.
-   CHF reporting is common but not guaranteed.
-   Multinational issuers require careful currency and accounting-standard
    handling.

Release standard

-   Public Switzerland support requires issuer/source provenance and explicit
    accounting-standard handling.

#### Japan

Branch

-   `japan`

Primary sources to investigate

-   EDINET
-   Tokyo Stock Exchange issuer metadata
-   issuer annual reports

Accounting and market issues

-   Japanese GAAP, IFRS and U.S. GAAP may appear.
-   JPY reporting is common.
-   Japanese-language labels and XBRL taxonomy mapping require dedicated tests.

Release standard

-   Public Japan support requires EDINET/issuer-source provenance and tested
    Japanese taxonomy mapping.

#### South Korea

Branch

-   `south_korea`

Primary sources to investigate

-   DART / OpenDART
-   Korea Exchange issuer metadata
-   issuer annual reports

Accounting and market issues

-   Korean IFRS is common.
-   KRW reporting is common.
-   Korean-language source labels require deterministic mapping.

Release standard

-   Public South Korea support requires DART/OpenDART-source provenance and
    tested Korean taxonomy mapping.

#### Hong Kong

Branch

-   `hong_kong`

Primary sources to investigate

-   HKEXnews
-   SFC where applicable
-   issuer annual reports

Accounting and market issues

-   IFRS/HKFRS mapping.
-   HKD, CNY and USD reporting may appear.
-   Mainland/Hong Kong dual listings need issuer identity mapping.

Release standard

-   Public Hong Kong support requires HKEX/issuer-source provenance and
    currency/dual-listing controls.

#### Singapore

Branch

-   `singapore`

Primary sources to investigate

-   SGXNet
-   ACRA where applicable
-   issuer annual reports

Accounting and market issues

-   IFRS/SFRS(I) mapping.
-   SGD and USD reporting may appear.
-   REITs and business trusts need separate classification.

Release standard

-   Public Singapore support requires SGX/issuer-source provenance and trust
    structure handling.

### Deferred Markets

The following markets remain research-only until a market-specific source,
normalization and validation plan is written:

-   Italy
-   Spain
-   Sweden
-   Denmark
-   Belgium
-   Taiwan
-   Finland
-   Norway
-   Ireland
-   Austria
-   Portugal
-   India
-   Brazil
-   Mexico
-   Poland
-   Czech Republic
-   Greece
-   Romania
-   Hungary
-   Middle East
-   Additional emerging markets

------------------------------------------------------------------------

# Track C --- Platform

Desktop

-   Windows
-   macOS
-   Linux

Mobile

-   iOS
-   Android

Future Terminal

-   Multi-window workspace
-   Offline cache
-   Push notifications
-   Cross-device sync
-   Saved layouts
-   Keyboard shortcuts

Goal

Bloomberg Terminal for long-term investors.

------------------------------------------------------------------------

# Track D --- Premium Data Expansion

Only begin after recurring revenue justifies licensing.

Phase 1

-   Option chains
-   Greeks
-   IV Rank
-   IV Percentile
-   Volatility surface

Phase 2

-   Corporate bond pricing
-   Credit spreads
-   Yield to maturity
-   Yield to worst
-   Duration
-   Convexity
-   Bond liquidity
-   Bond scoring

Phase 3

-   Alternative data
-   Institutional execution metrics
-   Advanced liquidity analytics

Deferred portfolio data features

-   Option-aware portfolio risk needs option chains, Greeks, IV Rank,
    IV Percentile and volatility surface data.
-   Fixed-income portfolio analytics need corporate bond pricing, credit
    spreads, yield to maturity, yield to worst, duration, convexity and bond
    liquidity.
-   Full tax-lot optimization needs broker-imported lots, realized gain/loss
    records and jurisdiction-specific tax rules.
-   Full dividend-income forecasting needs point-in-time dividend history,
    announced future dividends, withholding tax rules and corporate-action
    adjusted payout records.
-   Execution-quality analytics need institutional execution metrics,
    bid/ask history, market-impact estimates and intraday volume curves.

Provider rule

Changing providers must only require replacing the adapter.

------------------------------------------------------------------------

# Track E --- Data Infrastructure

This track is foundational.

Implement

-   Point-in-time database
-   Historical index constituents
-   Delisted companies
-   Filing version history
-   Financial restatement tracking
-   Corporate actions
-   Split history
-   Dividend history
-   FX history
-   Symbol mapping
-   ISIN mapping
-   CUSIP mapping
-   SEDOL mapping
-   Global identifier service

Goal

Institutional-grade historical research with minimal survivorship and
look-ahead bias.

------------------------------------------------------------------------

# AI Implementation Rules

1.  Never hard-code vendor-specific fields.
2.  Normalize data before calculations.
3.  Engines must be stateless where possible.
4.  Every engine must expose reusable APIs.
5.  Every feature must support feature flags.
6.  Every engine requires documentation, methodology, assumptions and
    limitations.
7.  Architecture takes priority over feature velocity.
8.  Expensive APIs are deferred until justified by customer demand and
    revenue.
9. every version/track after launch gets a new branch, never push to main branch 
10. country implementation must be independent so if one country can go live first it will go live 
11. every country branch must include its own country-specific release README before any publication decision
12. this file should never get commited since it shows our future releases 
Success Metric

Build the complete architecture first.

Ship features gradually.

Avoid rewrites.
