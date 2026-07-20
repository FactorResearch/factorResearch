# Build-vs-Buy and No-Reinvention Policy

# Purpose

Prevent AI coding agents from creating expensive, unsafe, or redundant infrastructure when a mature maintained library or managed component already solves the responsibility.

# Governing rule

Cenvarn builds the financial and product semantics that create its moat. Cenvarn does not rebuild commodity infrastructure, protocols, cryptographic primitives, storage engines, transport layers, numerical foundations, or rendering engines.

A request to improve speed, reduce memory, use Rust, remove dependencies, or avoid vendor lock-in is **not** permission to replace mature infrastructure with custom code.

# Cenvarn-owned code

The following are valid areas for project-owned Python, Rust, SQL, or TypeScript implementations because their meaning is part of the product and must be independently certifiable:

- Financial formulas, model definitions, scoring conventions, factor ranking, exclusions, tie-breaking, and missing-data policies.
- Point-in-time availability rules, filing selection, fiscal-period mapping, financial normalization mappings, provenance, and confidence rules.
- Corporate-action interpretation and the rules for adjusted price and total-return construction.
- Portfolio transaction-ledger semantics, valuation policy, attribution, cost-basis rules, and supported account events.
- Backtesting event sequencing, rebalancing rules, transaction-cost policy, benchmark policy, survivorship controls, and leakage prevention.
- Simulation specifications, scenario definitions, deterministic seeding policy, and financial interpretation.
- Immutable computation identities, model/data manifests, cache invalidation identities, resource budgets, and product entitlement rules.
- Narrow adapters that isolate approved providers and libraries behind Cenvarn-owned interfaces.

# Do not build

An AI agent must not create, substantially reimplement, or replace the following with custom Python, Rust, C++, TypeScript, or shell code unless an accepted ADR explicitly authorizes the exception:

- HTTP clients, connection pools, HTTP parsers, TLS stacks, web servers, reverse proxies, CDN behavior, or RPC protocol implementations.
- PostgreSQL drivers, connection-pool implementations, database engines, SQL parsers, migration engines, object stores, or custom relational persistence layers.
- Workflow engines, durable queues, schedulers, retry engines, lease systems, distributed locks, message brokers, or job-history stores when the selected platform already provides them.
- Redis or Valkey servers, RESP clients, cache protocols, general-purpose cache engines, or distributed rate-limit primitives.
- Cryptographic algorithms, random-number generators, password hashing, JWT/JWS/JWE implementations, OAuth/OIDC protocols, key management, certificate validation, or webhook-signature primitives.
- Payment clients, payment-state protocols, tax engines, card handling, or Stripe-compatible SDK replacements.
- XML, HTML, XBRL, JSON, CSV, Arrow, Parquet, compression, encoding, serialization, or schema-language parsers and writers. Cenvarn may own financial normalization after parsing.
- DataFrame engines, SQL query engines, vector databases, columnar formats, memory allocators, general-purpose collections, or concurrency runtimes.
- Matrix decomposition, BLAS, LAPACK, Cholesky, QR, SVD, eigensolvers, statistical-distribution primitives, or generic optimization algorithms when a maintained library exists.
- Date, time-zone, calendar, currency-code, UUID, decimal-arithmetic, or locale libraries.
- Charting, Canvas, WebGL, PDF rendering, spreadsheet rendering, accessibility engines, browser frameworks, or design-system foundations.
- Logging, tracing, metrics protocols, OpenTelemetry SDKs, error-reporting clients, vulnerability scanners, dependency resolvers, package managers, test runners, linters, formatters, or build systems.
- A custom C++ application layer. C++ may be consumed indirectly through mature dependencies but must not be introduced as a Cenvarn-owned runtime without an accepted ADR.

# Approved implementation direction

Use maintained libraries and platforms through narrow project-owned interfaces. Current preferred direction includes:

- HTTPX or another approved maintained client for new Python HTTP transport.
- Psycopg for PostgreSQL.
- FastAPI/Pydantic and an approved ASGI server for API delivery.
- PyJWT and cryptography for token and cryptographic primitives.
- Stripe's official SDK for billing integration.
- lxml or another approved parser for XML/HTML parsing.
- Arrow and Parquet for cross-language and persisted analytical data.
- Polars and DuckDB for columnar ETL and analytical querying where appropriate.
- PyO3 and maturin for Python/Rust integration and packaging.
- `ndarray`, `faer`, maintained random/distribution crates, and tested decimal/date crates in Rust.
- A selected durable workflow platform rather than another custom queue.
- Next.js/React/TypeScript, ECharts, and Lightweight Charts for the customer product.
- Valkey or Redis-compatible maintained infrastructure for ephemeral coordination only.

These choices may change through the architecture process. The rule against rebuilding their responsibilities remains in force.

# Rust boundary

Rust is approved for deterministic CPU-heavy financial computation, compact data structures, matrix processing, portfolio replay, factor ranking, backtesting, simulations, and financial normalization after standard parsing.

Rust is not approved merely to reduce the dependency count or because a component could theoretically be faster. Moving a responsibility to Rust requires an appropriate ownership boundary, canonical schemas, correctness fixtures, realistic end-to-end benchmarks, packaging support, telemetry, and rollback.

# Mandatory pre-code check

Before adding a new subsystem or more than a small utility, the AI must answer internally and record in the issue or PR when material:

1. Does an approved dependency or platform already own this responsibility?
2. Is this Cenvarn-specific business meaning or commodity infrastructure?
3. Can the requirement be met by configuration, an adapter, a query, or composition instead of new infrastructure?
4. Will this code duplicate protocol, persistence, retry, parsing, numerical, or rendering behavior maintained elsewhere?
5. What is the long-term security, update, test, operational, and migration burden?

If the responsibility is commodity infrastructure, stop and use the approved library or request an architecture decision.

# Exception process

An exception requires all of the following before implementation:

- A dedicated issue and accepted ADR naming the exact responsibility to replace.
- Evidence that maintained alternatives were evaluated and cannot meet a documented requirement.
- Production-shaped benchmarks including conversion, serialization, operations, memory, and failure behavior.
- Security, privacy, licensing, supply-chain, maintenance, observability, rollout, and rollback review.
- A bounded scope that does not expand into rebuilding adjacent infrastructure.
- Explicit user approval.

An AI agent must not create the exception ADR and then treat its own proposal as approved. Until approval exists, the mature implementation remains mandatory.

# Review and completion gate

A task is incomplete when it:

- duplicates an approved dependency;
- contains a home-grown protocol or infrastructure subsystem without an accepted exception;
- introduces Rust or another language without a justified ownership boundary;
- replaces a library based only on a microbenchmark;
- removes a fallback before parity and runtime certification;
- hides a custom reimplementation behind a misleading name such as helper, lightweight client, simple queue, mini framework, internal parser, or temporary adapter.

Reviews must inspect behavior, not names. Small custom implementations of prohibited responsibilities remain prohibited.