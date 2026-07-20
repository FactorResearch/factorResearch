# READ THIS ONLY

# Purpose

This is the only starting document for any AI working on Factor Research.

When the user says `Run ISSUE_046`, the AI must handle the rest automatically.

# Required workflow

1. Find the requested issue in **Factor Research — Technical Issue Tracker**.
2. Read the full issue, including status, dependencies, parent and child issues, linked Epic, Components, Release, Architecture Decisions, files, constraints, and acceptance criteria.
3. Automatically read only the linked ADRs, related issues, components, and documentation needed for that issue.
4. Inspect the repository before making changes. The current codebase is the implementation source of truth.
5. Determine what is already complete, what is missing, and whether the issue contains outdated assumptions.
6. Implement the issue completely without duplicating existing systems.
7. Add or update automated tests and run the relevant test suite.
8. Fix regressions introduced by the change.
9. Verify every acceptance criterion.
10. Update the Notion issue with status, files changed, implementation summary, test results, remaining risks, and GitHub PR link when available.
11. Mark the issue **Done** only when all acceptance criteria pass.
12. Return only a concise completion message, for example: `ISSUE_046 done. Notion updated.`

# Rules

- Do not ask the user which ADR, dependency, component, or document to read. Discover them automatically.
- Do not ask the user to repeat information already available in Notion or the repository.
- Do not blindly follow stale issue text when the repository has changed. Reconcile the issue with the current implementation.
- ADRs define architectural intent. If an issue conflicts with a linked accepted ADR, preserve the ADR and document the conflict.
- Never expose raw internal errors, secrets, credentials, tokens, or private data.
- Prefer reliability, maintainability, testability, and graceful degradation.
- All new and modified code must comply with `ISSUE_076`: practical SOLID principles, clean dependency boundaries, narrow interfaces, composition over inheritance, dependency inversion at volatile boundaries, and automated quality gates.
- When an issue touches existing code, apply `ISSUE_077`: protect current behavior with characterization tests, improve the affected area incrementally, and do not expand legacy coupling. Any justified deferral must record the risk, scope, owner, and removal trigger.
- Do not create god classes, god components, duplicated business logic, hidden dependencies, framework-coupled domain code, oversized interfaces, or abstractions without a real source of variation.
- Before marking any issue Done, run the SOLID review checklist and required architecture, lint, type, test, duplication, circular-dependency, and contract checks relevant to the changed code.
- A failure in one Analyze or Portfolio section must not break the whole page.
- Core cards and essential analysis take priority over optional graphs and background work.
- Never mark work Done when tests fail or acceptance criteria remain incomplete.

# Mandatory build-vs-buy guardrail

Before writing code, the AI must load and apply `Build-vs-Buy-and-No-Reinvention-Policy.md`.

The AI must distinguish Cenvarn-specific financial or product semantics from commodity infrastructure. It may implement Cenvarn's financial formulas, point-in-time rules, portfolio ledger semantics, factor ranking, backtesting behavior, simulation policy, normalization mappings, computation identities, and narrow adapters.

Without an accepted ADR and explicit user approval, the AI must **not** implement custom replacements for HTTP or RPC stacks, web servers, database drivers or engines, workflow or queue engines, cache servers or protocols, cryptography, authentication protocols, payment SDKs, parsers and serializers, Arrow or Parquet, compression, DataFrame or query engines, numerical decomposition libraries, random-number generators, date/time/currency/decimal foundations, charting engines, observability SDKs, package/build/test tooling, or a custom C++ runtime.

The following labels do not bypass this rule: `helper`, `lightweight client`, `simple queue`, `mini framework`, `internal parser`, `temporary adapter`, `optimized replacement`, or `small Rust service`. Review the responsibility actually implemented.

If an issue appears to request prohibited code, stop that portion, use the approved maintained dependency through a narrow Cenvarn-owned interface, and document the conflict. An exception requires a dedicated issue, accepted ADR, alternative evaluation, production-shaped benchmarks, security and maintenance review, rollback, and explicit user approval.

# User command format

The user only needs to say:

`Run ISSUE_046`

The AI must perform the entire workflow above without requiring additional instructions unless instruction can be helpful to prevent rewrite.

# Remaining issues

This list mirrors the unresolved execution order in [Issue Fix Order Map](https://app.notion.com/p/Issue-Fix-Order-Map-39f4ef32c9f7812d8214e861e966e4e2?pvs=21). Completed issues are intentionally omitted.

## Wave 0 — Toolchain and canonical contracts

- [ISSUE_145 — Modernize Dependency Management, Upgrade Stale Libraries & Add Supply-Chain Gates](https://app.notion.com/p/Modernize-Dependency-Management-Upgrade-Stale-Libraries-Add-Supply-Chain-Gates-3a34ef32c9f78178a077f0259ef460bf?pvs=21)
- [ISSUE_137 — Establish Language-Neutral Canonical Schemas, Typed Missingness & Arrow Boundaries](https://app.notion.com/p/Establish-Language-Neutral-Canonical-Schemas-Typed-Missingness-Arrow-Boundaries-3a34ef32c9f7819ea5a3eb61fdf577cb?pvs=21)

## Wave 1 — Startup, identity, user data, and distributed execution

- [ISSUE_126 — Serialize Database Initialization and Migrations Across Processes](https://app.notion.com/p/Serialize-Database-Initialization-and-Migrations-Across-Processes-3a34ef32c9f781ed8c80c2a4da6ed978?pvs=21)
- [ISSUE_116 — Migrate Portfolios & Simulations from Local Files to PostgreSQL with RLS](https://app.notion.com/p/Migrate-Portfolios-Simulations-from-Local-Files-to-PostgreSQL-with-RLS-3a34ef32c9f7810ea06cfb8e6859115a?pvs=21)
- [ISSUE_080 — Implement PostgreSQL Row-Level Security for All User-Owned Data](https://app.notion.com/p/Implement-PostgreSQL-Row-Level-Security-for-All-User-Owned-Data-3a24ef32c9f781a7b120e9c09a6dc186?pvs=21)
- [ISSUE_082 — Enforce PostgreSQL Least-Privilege Roles & Service Account Separation](https://app.notion.com/p/Enforce-PostgreSQL-Least-Privilege-Roles-Service-Account-Separation-3a24ef32c9f7816592a3fd815562f748?pvs=21)
- [ISSUE_120 — Prevent Concurrent Idempotency Claims from Executing Duplicate Side Effects](https://app.notion.com/p/Prevent-Concurrent-Idempotency-Claims-from-Executing-Duplicate-Side-Effects-3a34ef32c9f781a38cb8de396e2ca9f5?pvs=21)
- [ISSUE_144 — Consolidate Custom Job Systems onto a Durable Workflow Engine](https://app.notion.com/p/Consolidate-Custom-Job-Systems-onto-a-Durable-Workflow-Engine-3a34ef32c9f781eaa5b6d97340a98a55?pvs=21)
- [ISSUE_128 — Make Adaptive UI Jobs Distributed, Durable and Truly Resumable](https://app.notion.com/p/Make-Adaptive-UI-Jobs-Distributed-Durable-and-Truly-Resumable-3a34ef32c9f78187b3d0c1408350612f?pvs=21)
- [ISSUE_129 — Fix Analysis Queue Starvation, Processing Leases and Multi-Worker Recovery](https://app.notion.com/p/Fix-Analysis-Queue-Starvation-Processing-Leases-and-Multi-Worker-Recovery-3a34ef32c9f781f085eae3e8c6342537?pvs=21)
- [ISSUE_127 — Prevent Provider Tokens and Cookie Sessions from Outliving Authentication](https://app.notion.com/p/Prevent-Provider-Tokens-and-Cookie-Sessions-from-Outliving-Authentication-3a34ef32c9f781caadbafcd4f7eb0a44?pvs=21)
- [ISSUE_130 — Separate Cookie CSRF Enforcement from Bearer API Authentication](https://app.notion.com/p/Separate-Cookie-CSRF-Enforcement-from-Bearer-API-Authentication-3a34ef32c9f781088aadcdb93662bc92?pvs=21)
- [ISSUE_136 — Wire First-Party Access Tokens into Every Protected API Route](https://app.notion.com/p/Wire-First-Party-Access-Tokens-into-Every-Protected-API-Route-3a34ef32c9f781859d40d53c22d42fa3?pvs=21)
- [ISSUE_131 — Complete Account Erasure Across Databases, Redis, Jobs, Caches and Audit Records](https://app.notion.com/p/Complete-Account-Erasure-Across-Databases-Redis-Jobs-Caches-and-Audit-Records-3a34ef32c9f7816f8935f1af532db543?pvs=21)
- [ISSUE_087 — Establish Production Secret Management, Rotation & Leak Response](https://app.notion.com/p/Establish-Production-Secret-Management-Rotation-Leak-Response-3a24ef32c9f781079abafc25dc749e4b?pvs=21)
- [ISSUE_085 — Implement Admin RBAC, Mandatory MFA & Step-Up Authentication](https://app.notion.com/p/Implement-Admin-RBAC-Mandatory-MFA-Step-Up-Authentication-3a24ef32c9f781ecb85bd212a2367917?pvs=21)
- [ISSUE_086 — Add Server-Side Session Inventory, Device Revocation & Global Logout](https://app.notion.com/p/Add-Server-Side-Session-Inventory-Device-Revocation-Global-Logout-3a24ef32c9f781d6a63ec5633bbc2bd6?pvs=21)
- [ISSUE_134 — Separate Liveness from Dependency-Aware Readiness Probes](https://app.notion.com/p/Separate-Liveness-from-Dependency-Aware-Readiness-Probes-3a34ef32c9f781c9a170e119d6b93e6f?pvs=21)

## Wave 2 — Legal and financial foundation

- [ISSUE_097 — Establish Investment-Research Regulatory Boundary & Marketing Review](https://app.notion.com/p/Establish-Investment-Research-Regulatory-Boundary-Marketing-Review-3a24ef32c9f7819b9a7ee1044c711aae?pvs=21)
- [ISSUE_090 — Define Data Classification, Retention, Privacy Rights & Vendor Compliance](https://app.notion.com/p/Define-Data-Classification-Retention-Privacy-Rights-Vendor-Compliance-3a24ef32c9f7816683ffc433e7cd0038?pvs=21)
- [ISSUE_092 — Capture Subscription Legal Consent & Versioned Contract Evidence](https://app.notion.com/p/Capture-Subscription-Legal-Consent-Versioned-Contract-Evidence-3a24ef32c9f781e8961fe9f770b51d57?pvs=21)
- [ISSUE_096 — Implement Sales-Tax Registration, Stripe Tax & Filing Operations](https://app.notion.com/p/Implement-Sales-Tax-Registration-Stripe-Tax-Filing-Operations-3a24ef32c9f7813c9c15d2318510e22b?pvs=21)

## Wave 3 — Monetization, billing, entitlements, cancellation, and refunds

- [ISSUE_135 — Close the Public Cached-Analysis API Paywall and Usage-Limit Bypass](https://app.notion.com/p/Close-the-Public-Cached-Analysis-API-Paywall-and-Usage-Limit-Bypass-3a34ef32c9f78101941df98b0e432db8?pvs=21)
- [ISSUE_093 — Build Durable Stripe Webhook Processing, Ordering & Reconciliation](https://app.notion.com/p/Build-Durable-Stripe-Webhook-Processing-Ordering-Reconciliation-3a24ef32c9f781d7aabbe8f2cbffc23e?pvs=21)
- [ISSUE_094 — Create Subscription Audit Ledger & Entitlement State Machine](https://app.notion.com/p/Create-Subscription-Audit-Ledger-Entitlement-State-Machine-3a24ef32c9f781a08e10ceb8a252e640?pvs=21)
- [ISSUE_095 — Implement Refund, Cancellation, Renewal Notice & Dispute Workflows](https://app.notion.com/p/Implement-Refund-Cancellation-Renewal-Notice-Dispute-Workflows-3a24ef32c9f781338407d2e0bc248c8e?pvs=21)

## Wave 4 — Provider continuity, cache safety, recovery, and incidents

- [ISSUE_114 — Make Market-Data Cache Keys, Freshness & Corporate-Action Invalidation Complete](https://app.notion.com/p/Make-Market-Data-Cache-Keys-Freshness-Corporate-Action-Invalidation-Complete-3a34ef32c9f7812a933ec243e2131c75?pvs=21)
- [ISSUE_115 — Build Distributed Provider Quotas, Accurate Failure Classification & SEC Identity](https://app.notion.com/p/Build-Distributed-Provider-Quotas-Accurate-Failure-Classification-SEC-Identity-3a34ef32c9f781a4892fefc97861f717?pvs=21)
- [ISSUE_121 — Make File-Cache Writes Atomic & Surface Corruption Instead of Silent Misses](https://app.notion.com/p/Make-File-Cache-Writes-Atomic-Surface-Corruption-Instead-of-Silent-Misses-3a34ef32c9f781f3a2cbf546aec26358?pvs=21)
- [ISSUE_083 — Build Encrypted Backups, Point-in-Time Recovery & Restore Verification](https://app.notion.com/p/Build-Encrypted-Backups-Point-in-Time-Recovery-Restore-Verification-3a24ef32c9f781c5b797fd4a3dbfd5d7?pvs=21)
- [ISSUE_084 — Centralize Security Monitoring, Detection Rules & Alert Escalation](https://app.notion.com/p/Centralize-Security-Monitoring-Detection-Rules-Alert-Escalation-3a24ef32c9f7818084a9f5c4ea027800?pvs=21)
- [ISSUE_089 — Harden Production Edge, Network, Containers & Origin Access](https://app.notion.com/p/Harden-Production-Edge-Network-Containers-Origin-Access-3a24ef32c9f781018d55e25ccff54ac8?pvs=21)
- [ISSUE_091 — Create Security Incident Response, Breach Handling & Tabletop Exercises](https://app.notion.com/p/Create-Security-Incident-Response-Breach-Handling-Tabletop-Exercises-3a24ef32c9f781d2829ce5c958b3024f?pvs=21)

## Wave 5 — Financial engine, storage, and freshness correctness

- [ISSUE_123 — Fix Live Portfolio Valuation, Current Weights & Invalid Price Handling](https://app.notion.com/p/Fix-Live-Portfolio-Valuation-Current-Weights-Invalid-Price-Handling-3a34ef32c9f78131bc06c58a34a9315e?pvs=21)
- [ISSUE_124 — Correct SEC Annual Fact Selection, Amendments & Concept-Coverage Rules](https://app.notion.com/p/Correct-SEC-Annual-Fact-Selection-Amendments-Concept-Coverage-Rules-3a34ef32c9f781078ebae220b1aeadc8?pvs=21)
- [ISSUE_133 — Replace Single-Precision Financial Columns and Free-Form Timestamps](https://app.notion.com/p/Replace-Single-Precision-Financial-Columns-and-Free-Form-Timestamps-3a34ef32c9f78135ad21c68d6922dfe7?pvs=21)
- [ISSUE_132 — Enforce Analysis Cache Freshness and Automatic Revalidation](https://app.notion.com/p/Enforce-Analysis-Cache-Freshness-and-Automatic-Revalidation-3a34ef32c9f78191a121dd767cfd99c5?pvs=21)
- [ISSUE_110 — Use Split- and Dividend-Adjusted Total-Return Histories in Every Backtest](https://app.notion.com/p/Use-Split-and-Dividend-Adjusted-Total-Return-Histories-in-Every-Backtest-3a34ef32c9f78137bc0af788057c3495?pvs=21)
- [ISSUE_113 — Preserve Valid Zero Scores & Fix Missing-Data Warning Semantics](https://app.notion.com/p/Preserve-Valid-Zero-Scores-Fix-Missing-Data-Warning-Semantics-3a34ef32c9f781e3a0cbc5bfca851434?pvs=21)
- [ISSUE_117 — Fingerprint Strategy Cache from Actual Data, Universe & Model Versions](https://app.notion.com/p/Fingerprint-Strategy-Cache-from-Actual-Data-Universe-Model-Versions-3a34ef32c9f7816f967bccdec94f51fa?pvs=21)
- [ISSUE_109 — Stop Factor Lab Look-Ahead Bias & Repair the SPY Benchmark Contract](https://app.notion.com/p/Stop-Factor-Lab-Look-Ahead-Bias-Repair-the-SPY-Benchmark-Contract-3a34ef32c9f781aab609e5a294146b65?pvs=21)
- [ISSUE_111 — Rebuild Portfolio Backtests from Transactions, Acquisition Dates & Cash Flows](https://app.notion.com/p/Rebuild-Portfolio-Backtests-from-Transactions-Acquisition-Dates-Cash-Flows-3a34ef32c9f781d99c82ed7a197815c8?pvs=21)
- [ISSUE_112 — Correct Monte Carlo Calendar Alignment, Weights, Covariance & Fallback Behaviour](https://app.notion.com/p/Correct-Monte-Carlo-Calendar-Alignment-Weights-Covariance-Fallback-Behaviour-3a34ef32c9f7812a8cc2d7e4eac83089?pvs=21)
- [ISSUE_118 — Preserve SEC Fact Identity, Filing Provenance & Amendment History](https://app.notion.com/p/Preserve-SEC-Fact-Identity-Filing-Provenance-Amendment-History-3a34ef32c9f781a78f84c97d8281be4d?pvs=21)

## Wave 5A — Immutable analytical data foundation

- [ISSUE_143 — Add a Parquet/Object-Storage Analytical Data Plane with Arrow, Polars & DuckDB](https://app.notion.com/p/Add-a-Parquet-Object-Storage-Analytical-Data-Plane-with-Arrow-Polars-DuckDB-3a34ef32c9f781c9be04d2f9a66ef829?pvs=21)

## Wave 6 — Quantitative validation and correctness evidence

- [ISSUE_079 — Build a 20-Year Realistic Algorithm Validation & Failure Attribution Backtest](https://app.notion.com/p/Build-a-20-Year-Realistic-Algorithm-Validation-Failure-Attribution-Backtest-3a04ef32c9f7812d9742cc51638ce87d?pvs=21)
- [ISSUE_122 — Create a Financial-Correctness Golden Gate for Backtests, Scores & Simulations](https://app.notion.com/p/Create-a-Financial-Correctness-Golden-Gate-for-Backtests-Scores-Simulations-3a34ef32c9f78124beccee469be73a69?pvs=21)

## Wave 7 — Native financial and quantitative architecture

- [ISSUE_138 — Build a Permanent Rust Price Matrix, Corporate-Action & FX Adjustment Engine](https://app.notion.com/p/Build-a-Permanent-Rust-Price-Matrix-Corporate-Action-FX-Adjustment-Engine-3a34ef32c9f7817aa698df0ab8e38e14?pvs=21)
- [ISSUE_140 — Migrate Portfolios to an Immutable Transaction Ledger & Native Valuation Engine](https://app.notion.com/p/Migrate-Portfolios-to-an-Immutable-Transaction-Ledger-Native-Valuation-Engine-3a34ef32c9f78133b01ce869e9f412c6?pvs=21)
- [ISSUE_139 — Build a General Event-Driven Point-in-Time Backtesting Engine in Rust](https://app.notion.com/p/Build-a-General-Event-Driven-Point-in-Time-Backtesting-Engine-in-Rust-3a34ef32c9f7811f9786f9967eb8d0b4?pvs=21)
- [ISSUE_099 — Build a Rust-Accelerated Quantitative Engine with Python Fallback](https://app.notion.com/p/Build-a-Rust-Accelerated-Quantitative-Engine-with-Python-Fallback-3a34ef32c9f781a18a27c9cb5a080c27?pvs=21)
- `ISSUE_100–108` — Execute native-kernel child issues under ISSUE_099

## Wave 8 — Security verification and migration prerequisites

- [ISSUE_088 — Create End-to-End Authentication, CSRF & Tenant-Isolation Security Tests](https://app.notion.com/p/Create-End-to-End-Authentication-CSRF-Tenant-Isolation-Security-Tests-3a24ef32c9f7819e8bf9e804c231b37b?pvs=21)
- Complete the legacy Dash open-issue audit required by `ISSUE_142` and classify remaining work as shared/backend, migrate, temporary compatibility, or superseded.

## Wave 9 — Typed product API and customer frontend

- [ISSUE_141 — Build a Typed FastAPI v2 Control Plane & Generated Client Contracts](https://app.notion.com/p/Build-a-Typed-FastAPI-v2-Control-Plane-Generated-Client-Contracts-3a34ef32c9f781e2aeacf08e006b2cdf?pvs=21)
- [ISSUE_142 — Replace Customer-Facing Dash with Next.js, TypeScript & Client-Side Chart Libraries](https://app.notion.com/p/ISSUE_142-Replace-Dash-Entirely-with-Next-js-3a34ef32c9f7817da44afd64a37c8de0?pvs=21)

## Wave 9A — Server efficiency, edge delivery, and throughput per dollar

- [ISSUE_146 — Maximize Server Efficiency, Throughput per Dollar & Resource-Light Operation](https://app.notion.com/p/Maximize-Server-Efficiency-Throughput-per-Dollar-Resource-Light-Operation-3a34ef32c9f781d09a35c7505140fedd?pvs=21)
- [ISSUE_147 — Build Edge-First Static Delivery, Immutable Snapshots & Origin Shielding](https://app.notion.com/p/Build-Edge-First-Static-Delivery-Immutable-Snapshots-Origin-Shielding-3a34ef32c9f7811085cfecc475d56d0c?pvs=21)
- [ISSUE_148 — Precompute Shared Analyses, Deduplicate Computation & Use Immutable Computation Identities](https://app.notion.com/p/Precompute-Shared-Analyses-Deduplicate-Computation-Use-Immutable-Computation-Identities-3a34ef32c9f78104847bddf5f930f190?pvs=21)
- [ISSUE_149 — Run a Long-Lived Rust Quant Service with Shared Memory-Mapped Datasets](https://app.notion.com/p/Run-a-Long-Lived-Rust-Quant-Service-with-Shared-Memory-Mapped-Datasets-3a34ef32c9f781019ef6c6a895bb7188?pvs=21)
- [ISSUE_150 — Use Bulk COPY, Staging Tables & Compact Wide Read Models](https://app.notion.com/p/Use-Bulk-COPY-Staging-Tables-Compact-Wide-Read-Models-3a34ef32c9f78149b6d4ec7d47ec98c4?pvs=21)
- [ISSUE_151 — Benchmark Database Keys, Indexes, Clustering & Partitioning Before Scale](https://app.notion.com/p/Benchmark-Database-Keys-Indexes-Clustering-Partitioning-Before-Scale-3a34ef32c9f781c39296e811f6c30c7c?pvs=21)
- [ISSUE_152 — Build a Lean ASGI Runtime with Bounded Concurrency, Backpressure & Server Benchmarks](https://app.notion.com/p/Build-a-Lean-ASGI-Runtime-with-Bounded-Concurrency-Backpressure-Server-Benchmarks-3a34ef32c9f7814caf19ea073c976810?pvs=21)
- [ISSUE_153 — Deliver Tiered API Payloads, Downsampled Charts & Lazy Detail Data](https://app.notion.com/p/Deliver-Tiered-API-Payloads-Downsampled-Charts-Lazy-Detail-Data-3a34ef32c9f78119a835cca77a029d3e?pvs=21)
- [ISSUE_154 — Add Micro-Batching, Priority Queues & Workload-Aware Scheduling](https://app.notion.com/p/Add-Micro-Batching-Priority-Queues-Workload-Aware-Scheduling-3a34ef32c9f781338850df1097e24b19?pvs=21)
- [ISSUE_155 — Enforce Resource Budgets, Cost Telemetry & Performance Regression Gates](https://app.notion.com/p/Enforce-Resource-Budgets-Cost-Telemetry-Performance-Regression-Gates-3a34ef32c9f7816bb5acdf7d2f79f5b0?pvs=21)

## Wave 10 — Monte Carlo presentation

- [ISSUE_081 — Add Monte Carlo Percentile Bands, Distribution Metrics & Scenario Interpretation](https://app.notion.com/p/Add-Monte-Carlo-Percentile-Bands-Distribution-Metrics-Scenario-Interpretation-3a24ef32c9f7816695b8f42889150c81?pvs=21)

## Wave 11 — International market correctness

- [ISSUE_119 — Enforce Strict Fiscal-Period Matching in Multi-Market Ingestion](https://app.notion.com/p/Enforce-Strict-Fiscal-Period-Matching-in-Multi-Market-Ingestion-3a34ef32c9f78151a734fb956f294e31?pvs=21)

## Final operational readiness and release command

- [ISSUE_156 — Define Release Cutline, Ownership & Go/No-Go Command System](https://app.notion.com/p/Define-Release-Cutline-Ownership-Go-No-Go-Command-System-3a34ef32c9f781a5b5a7f59e6ca515b8?pvs=21)
- [ISSUE_157 — Create Provider Data Licensing, Redistribution & Usage Register](https://app.notion.com/p/Create-Provider-Data-Licensing-Redistribution-Usage-Register-3a34ef32c9f781ce88c0d8dcf3185528?pvs=21)
- [ISSUE_158 — Build Customer Support, Account Recovery & Incident Operations Playbook](https://app.notion.com/p/Build-Customer-Support-Account-Recovery-Incident-Operations-Playbook-3a34ef32c9f781f29728dc65fa9e83eb?pvs=21)
- [ISSUE_083 — Complete the operational recovery amendment and restore the exact release architecture](https://app.notion.com/p/Build-Encrypted-Backups-Point-in-Time-Recovery-Restore-Verification-3a24ef32c9f781c5b797fd4a3dbfd5d7?pvs=21)
- [ISSUE_125 — Run production-like runtime tests against the exact release architecture](https://app.notion.com/p/Run-Production-Like-Runtime-Tests-and-Evidence-Based-Launch-Certification-3a34ef32c9f7812daa9aeaa2650a86b4?pvs=21)

When the Issue Fix Order Map changes, refresh this section. When an issue is completed, remove it from this list rather than retaining it as completed history.