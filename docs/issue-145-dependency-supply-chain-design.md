# ISSUE_145 dependency and supply-chain design

## Outcome

Developers and CI install the same reviewed Python and Node dependency graphs
from committed lockfiles. Every direct dependency has an owner and disposition,
and pull requests are blocked when they introduce an unacceptable vulnerability,
license, undeclared package, or unreviewed commodity-infrastructure replacement.

The internal customer is every contributor and release operator. The visible
product behavior is intentionally unchanged.

## Verified current behavior and root cause

The repository currently splits Python runtime, development, and proof tooling
across three requirements files. CI additionally installs pytest outside those
files, so the tested environment is not declared or locked. `pyproject.toml`
contains tool configuration only and there is no `uv.lock`.

Node installs already reproduce through `package-lock.json`, but the security
workflow produces only a Python SBOM. Existing pip and npm vulnerability checks
do not provide a pull-request dependency diff or a license policy. The root
agent-policy mirror, standards index, direct-dependency ownership record, and
grouped dependency updater are also absent.

The root cause is fragmented dependency ownership: manifests, CI installation,
security review, policy, and update automation evolved independently rather
than sharing one canonical declaration per ecosystem.

## Scope and non-goals

In scope:

- PEP 621 project metadata, PEP 735 dependency groups, `uv.lock`, and frozen
  Python synchronization.
- The existing npm manifest and lockfile, including a frozen integrity check.
- Explicit declarations for pytest, Hypothesis, and current CI tooling.
- An owner, disposition, license posture, upgrade policy, and removal trigger
  for every direct Python and Node dependency.
- Python and Node vulnerability scans and CycloneDX SBOMs.
- License-aware dependency review and grouped scheduled updates.
- Root agent instructions, the repository standards index, and build-versus-buy
  pull-request questions.
- Compatibility tests for major dependency versions shipped by this change.

Non-goals:

- Adding FastAPI, Pydantic settings, HTTPX, Arrow, Polars, DuckDB, Temporal,
  PyO3, maturin, ECharts, or Lightweight Charts before their owning issues.
- Creating an empty Rust crate merely to produce `Cargo.lock`.
- Replacing Requests or Finnhub adapters, migrating Redis to Valkey, or
  replacing customer-facing Dash/Plotly pages.
- Changing financial formulas, public APIs, persistence, authorization, or UI.

## Existing capabilities reused

- `uv` owns Python resolution, environments, lockfiles, and frozen sync.
- npm owns Node resolution, lock integrity, audit, and CycloneDX SBOM output.
- pip-audit and CycloneDX Python own Python vulnerability and SBOM formats.
- GitHub's dependency-review action owns pull-request vulnerability and license
  diffs.
- Dependabot owns grouped update pull requests.
- Existing release, security, architecture, and product tests remain the
  authoritative compatibility suite.

No dependency resolver, scanner, license parser, SBOM writer, updater, package
manager, or commodity protocol is implemented by Cenvarn.

## Proposed ownership and contracts

`pyproject.toml` is the only hand-edited Python dependency declaration.
`uv.lock` is the generated exact resolution. Runtime dependencies use an
intentional compatible major range; development and audit tools live in named
dependency groups. CI must run `uv sync --frozen` before any Python check and
must not install undeclared packages.

`package.json` remains the Node declaration and `package-lock.json` remains the
exact resolution. CI must use `npm ci`.

The dependency inventory is a review contract, not executable package-manager
logic. Its rows must correspond exactly to direct declarations and state the
owning component/team, keep/temporary/replace/prohibited disposition, license,
purpose, upgrade boundary, and exit trigger.

The repository currently has no Rust package. Native dependency count and
compile time are therefore zero. A future issue that adds `Cargo.toml` must also
add `Cargo.lock`, cargo-audit, cargo-deny, compatibility tests, and a documented
compile-time budget in the same change. A placeholder crate would falsely claim
an architecture boundary and is explicitly excluded.

## Dependency upgrade policy

The lockfile resolves current stable releases within reviewed major ranges.
This issue may ship coordinated NumPy 2 / pandas 3, Plotly 6, current Psycopg,
Gunicorn, Flask-Limiter, Redis client, MarkupSafe, Stripe SDK, and quality-tool
major lines only when the complete compatibility suite passes on Python 3.12.
Python 3.13 is the next-minor compatibility lane. Yanked releases are excluded
by regeneration rather than manually editing the lockfile.

Architecture dependencies named in later issues remain absent even when they
are listed as a future direction in the issue. Temporary product dependencies
remain explicit so removal is tied to their owning migration rather than this
tooling change.

## Failure modes and degraded behavior

- A stale or edited lockfile makes frozen sync fail before tests run.
- A vulnerable dependency makes pip-audit, npm audit, or dependency review fail.
- A prohibited or unapproved license makes dependency review fail.
- An SBOM generation failure blocks the security job; incomplete SBOMs are not
  silently uploaded as success.
- Registry drift makes a repository regression test fail.
- A major-version incompatibility fails focused compatibility tests or the
  existing release gate and the upgrade is rolled back to the prior compatible
  major range.
- Scheduled updater failure does not change production state; it is visible in
  Actions/Dependabot and can be retried without side effects.

The workflows are idempotent, have no application data side effects, do not
require retries in project code, and contain no user or tenant data.

## Security, privacy, and authorization

The change processes only public package metadata and repository manifests. It
adds no secret, authentication, authorization, or tenant boundary. GitHub jobs
use read-only contents permissions except capabilities intrinsically required
by the hosted dependency service. SBOMs are build artifacts and must not contain
environment values or credentials.

## Financial and point-in-time implications

No formula or data-selection rule changes. NumPy/pandas upgrades are protected
by the full deterministic financial test suite, including golden and invariant
tests already in the repository. Any unexplained numeric difference blocks the
upgrade.

## Performance and resource implications

Frozen resolution removes resolver work from ordinary CI installs and uv reuses
its content-addressed cache. Security jobs add bounded package metadata and SBOM
work but no runtime dependency or customer request cost. Native dependency
count and Rust compile time remain zero.

## Observability

GitHub job status and uploaded Python/Node SBOM artifacts are the operational
record. Dependency review reports the rejected package, advisory severity, or
license. Lock and registry regression tests identify drift by file and field.
No application logging or alerts are appropriate because application runtime is
unchanged.

## Tests and acceptance evidence

- Structural tests parse `pyproject.toml`, package manifests, workflows, policy
  mirrors, and the direct-dependency inventory.
- Focused imports and representative NumPy/pandas, Plotly, Flask-Limiter,
  Psycopg, Redis, and Stripe surface checks protect upgraded public APIs.
- `uv lock --check` and `uv sync --frozen` prove lock consistency.
- `npm ci` proves Node lock integrity.
- pip-audit, npm audit, Python/Node SBOM generation, and dependency-review
  configuration cover separate supply-chain risks.
- The complete repository release gate proves application and financial
  compatibility on the supported Python version; a second CI lane tests Python
  3.13.

## Migration, rollout, and rollback

This is a two-way-door build change. CI switches atomically from ad-hoc pip
installs to frozen uv synchronization. No database or application rollout is
required.

Rollback restores the prior `pyproject.toml`, requirements files, lockfile
absence, and workflows from Git. A single incompatible library can instead be
rolled back by narrowing its declared major range and regenerating `uv.lock`.
The npm lockfile is regenerated only through npm and can be restored
independently. No persisted customer data is transformed.

## Smallest complete option

The design changes declarations, generated lock state, documentation, CI, and
their regression tests only. It does not add an application abstraction,
service, runtime package, empty Rust boundary, or custom supply-chain tool.

## Implementation reconciliation — 2026-07-21

The implemented lock resolves Dash 4.4.1, Plotly 6.9.0, pandas 3.0.3,
NumPy 2.5.1, Psycopg 3.3.4, Gunicorn 26.0.0, Flask-Limiter 4.1.1,
redis-py 8.0.1, MarkupSafe 3.0.3, Stripe 15.3.1, and the current compatible
quality-tool lines. Sass resolves to 1.101.3; its compiler ordering change was
accepted by regenerating tracked CSS from unchanged SCSS and making
`--no-source-map` explicit.

The undeclared-import audit found direct Jinja2 and PyYAML use that had been
masked by transitive installation. They are now direct runtime and development
declarations respectively. The unused `@axe-core/cli` wrapper was narrowed to
the directly consumed `axe-core`, removing Chromedriver and its vulnerable ZIP
dependency. The undeclared Psycopg 2 fallback was deleted rather than adding a
second PostgreSQL driver; Psycopg 3 is now the single persistence contract.

Python 3.12 is pinned and Python 3.13 has a compatibility lane. Node 24/npm 11
is the primary toolchain and Node 22/24 are a CI matrix. The repository still
contains no Rust package, so native dependency count and compile time remain
zero.

In-scope dependency tests, frozen sync/export, Python and Node SBOM generation,
pip-audit, npm audit, frontend lint, and SCSS parity pass. The repository-wide
completion gate remains blocked by failures already present in untouched
areas: missing architecture/design-system documents, one raw Dash button, and
a stale source-text factor-momentum assertion. These failures are not excluded
or weakened by ISSUE_145 and must be resolved before the issue can be marked
Done.
