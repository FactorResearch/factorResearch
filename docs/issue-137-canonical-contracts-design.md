# ISSUE_137 — Canonical financial contracts v1

## Outcome and verified gap

Cenvarn needs one versioned vocabulary for financial identities, exact values,
time, provenance, and missingness before native engines or API v2 are added.
The current provider dataclasses and V0.5 engine contracts are Python-only:
they use tickers as identity, free-form date strings, binary floats for exact
quantities, dictionaries for statements, implicit `None`, and pandas
DataFrames at engine boundaries. No Arrow, Rust, TypeScript, PostgreSQL, or
OpenAPI representation is checked against a common semantic source.

The user-visible effect is indirect but material: future engines and markets
can exchange data without silently changing identity, precision, time, units,
or the reason a value is unavailable.

## Scope and non-goals

This change adds the additive v1 contract foundation:

- a language-neutral JSON Schema and compatibility policy;
- typed Python domain records and exact JSON serialization;
- Arrow schemas and IPC validation for columnar price observations;
- aligned Rust Serde and TypeScript contract declarations;
- PostgreSQL type mappings and OpenAPI components;
- cross-language golden fixtures;
- compatibility adapters for legacy Date/Close DataFrames; and
- an architecture gate that prevents new untyped engine entry points.

It does not rewrite all engines, change production database tables, add
Parquet storage, migrate persisted provider records, introduce API v2, or move
financial calculations to Rust. Those are separate dependent issues.

## Existing code and dependency decision

The design reuses the repository's dataclass conventions, V0.5 contract tests,
architecture gate, uv lockfile, and existing pandas engines. Standard-library
`dataclasses`, `decimal`, `datetime`, `enum`, `json`, and `uuid` own the Python
domain meaning.

Apache Arrow is commodity infrastructure and must not be reimplemented.
PyArrow 25 is the maintained Apache implementation, supports the repository's
Python 3.12–3.13 range, uses the Apache-2.0 license, and provides platform
wheels. It is constrained to `>=25,<26` and locked with uv. Its material cost
is binary size and import memory; only boundary modules import it, and removal
means replacing those adapters with another standards-compliant Arrow
implementation rather than changing domain records.

Rust uses the maintained `serde`, `rust_decimal`, `time`, and `uuid` crates in
a schema-only crate; `serde_json` is test-only. Default features are narrowed,
the lockfile is committed, and the crate has no networking, storage, async
runtime, or financial-calculation dependency. TypeScript uses native
declarations and adds no package.

## Ownership and authoritative source

`schemas/canonical/v1/canonical.schema.json` is the language-neutral semantic
source. `codes/domain/canonical.py` owns Python validation and serialization.
`codes/core/arrow_contracts.py` owns Arrow physical schemas and IPC.
`codes/core/canonical_adapters.py` owns compatibility conversion at legacy
engine boundaries. Generated or parallel language representations must retain
the same `1.0.0` schema version and are checked by contract tests.

Provider adapters, API routes, repositories, and engines do not redefine the
meaning of these fields. Tickers remain aliases and are never used as the
permanent security or listing identifier in canonical records.

## Contracts and invariants

- Permanent entity, security, listing, and identifier IDs are UUID strings.
- Currency is an uppercase ISO-style three-letter code.
- Money, price, quantity, fees, taxes, and accounting facts use decimal text
  in JSON and `decimal128(38, 12)` in Arrow. No implicit rounding occurs.
- Ratios, returns, covariance, correlation, optimization, and simulation
  values use finite float64 only after a documented conversion boundary.
- Business dates are ISO dates. Event, availability, execution, and system
  times are timezone-aware UTC instants.
- Missingness is tagged as `available`, `missing`, `not_applicable`, `stale`,
  `invalid`, `provider_failed`, `insufficient_history`, or
  `policy_suppressed`; non-available values carry no numeric payload.
- Provenance identifies provider/source, observation and availability time,
  source record, normalization version, and optional filing version.
- Arrow fields include canonical schema and record-version metadata.
- IPC readers reject incompatible metadata or physical schemas before data is
  passed to an engine.

## Failure and degraded behavior

Construction rejects invalid UUIDs, currency codes, naive or non-UTC
timestamps, non-finite analytical numbers, empty provenance identifiers,
inconsistent missingness, non-positive prices, duplicate price dates, and
out-of-order observations. Decimal overflow or scale loss fails Arrow
conversion instead of silently rounding.

Compatibility conversion is deterministic, side-effect free, and performs no
retry or fallback. Malformed legacy frames fail with a typed `ValueError` at
the adapter boundary. No partial table is returned. IPC operations are local
and idempotent; concurrency, cancellation, restart, and network failure do not
apply.

## Security, privacy, and authorization

The contracts contain market and analytical data, not credentials or direct
personal data. They add no authentication or authorization behavior. Callers
remain responsible for tenant authorization before attaching user-owned
portfolio IDs. Golden fixtures use synthetic identifiers and must not contain
customer data. Validation errors describe fields but never payload contents.

## Financial and point-in-time correctness

Availability time is distinct from observation or fiscal-period dates so
historical engines can exclude facts that were not yet known. Filing version
and source record identifiers preserve amendments. Exact decimal fields do not
silently become binary floats. Missing values cannot become zero or neutral
scores. Units, currencies, price adjustment basis, provenance, model version,
and engine version are explicit where relevant.

## Performance and resource implications

Canonical dataclasses are immutable and slot-backed. Conversion is linear in
row count and creates one Arrow table at the boundary. IPC is used only when
crossing processes. This issue introduces no cache, background job, network
call, or unbounded retained state. Later performance-sensitive consumers must
benchmark copying and serialization before replacing existing paths.

## Observability

Pure domain and conversion functions do not log. Consumers should record the
schema version, record count, conversion duration, engine version, and failure
category with an existing correlation ID. Payload values, portfolio contents,
and provider credentials must not be logged. No new alert is warranted until
the contracts are used in a production workflow.

## Compatibility, migration, rollout, and rollback

Version `1.0.0` follows semantic compatibility: patches clarify constraints,
minor versions add optional fields or enum values only when consumers handle
unknown values, and major versions cover removals or meaning changes. Breaking
changes require side-by-side schemas, adapters, and data migrations.

Rollout is additive. Existing DataFrame engines remain unchanged and are fed
through named adapters by new consumers. Production database mappings are
documentation, not DDL; later migrations use expand-and-contract deployment.
Rollback removes the additive modules and PyArrow before dependent consumers
ship. There is no persisted data transformation or irreversible action.

## Test and acceptance evidence

Focused tests must prove:

- JSON and Arrow/IPC round trips retain permanent identity, exact decimals,
  missingness, UTC timestamps, units, currency, and provenance;
- JSON Schema, Python, Rust, TypeScript, PostgreSQL, OpenAPI, and Arrow expose
  the same version and required meanings;
- legacy DataFrames convert deterministically and malformed inputs fail closed;
- architecture checks reject newly added public engine functions that accept
  untyped dictionaries or pandas DataFrames; and
- existing engine behavior remains characterized by the current test suite.

The applicable release gate includes formatting, Ruff, strict mypy for the new
modules, focused tests, architecture/duplication checks, dependency audit, and
the repository release script. Pre-existing failures are reported without
weakening checks.

## Design-gate conclusion

The behavior is required because all dependent native and API work otherwise
creates incompatible one-off contracts. Existing Python-only dataclasses are
insufficient but are retained behind adapters. The standard library owns
domain meaning; Apache Arrow owns columnar interchange; PostgreSQL mappings
use native exact numeric and timezone-aware types. Direct, explicit modules
are smaller and safer than a code-generation framework at the current scale.
Rust is not used for computation. No existing production behavior should be
deleted in this foundation change.
