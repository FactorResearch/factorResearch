# Factor Research Architecture and SOLID Guardrails

## Dependency direction

Dependencies point inward toward stable financial rules:

```text
Presentation: codes.app, codes.routes, codes.app_modules
                         |
                         v
Application orchestration: codes.services, codes.engine
                         |
                         v
Domain: codes.models, codes.core financial contracts
                         ^
                         |
Ports: codes.core.ports and focused Protocol contracts
                         ^
                         |
Infrastructure: codes.data, provider, cache, database and vendor adapters
```

- Presentation validates transport input, renders output, and delegates work. It
  does not own financial formulas or vendor normalization.
- Application modules coordinate domain operations and transactions. Background
  workers call the same services instead of copying business rules.
- Domain calculations remain pure and do not import Flask, Dash, database
  drivers, HTTP clients, vendor SDKs, environment variables, or adapters.
- Ports are narrow, consumer-oriented `Protocol` types. Infrastructure maps
  database rows and vendor payloads to canonical/domain values at the boundary.
- A shared interface preserves units, nullability, freshness, errors, and
  financial meaning for every implementation.

## Composition roots

`codes.composition.compose_runtime` is the backend composition root for
process-wide volatile dependencies. `codes.app` calls it while assembling the
Flask/Dash process. Tests may inject deterministic clocks and ID sources.

`codes.app_modules.composition.compose_dash_ui` is the frontend composition
root. It registers feature callback adapters and assembles the shared layout.
Feature modules receive focused values/services and must not import the process
entry point.

Only composition roots construct concrete implementations. Do not pass the
container through the application as a service locator.

## Extension points

- Market/provider adapters implement the canonical contracts in
  `codes.data.providers`.
- Volatile quote, filing, persistence, time, and ID capabilities use focused
  ports in `codes.core.ports`.
- Financial engines publish schemas through `codes.core.engine_contracts` and
  reuse `codes.core.financial_math`.
- UI variants compose shared primitives. New variants must not copy financial
  calculations, callback orchestration, or page-specific SCSS.

Add an abstraction only when a real implementation boundary or source of
variation exists. Prefer a cohesive concrete function to a speculative
framework, and composition to inheritance.

## Automated gates

`scripts/release-gate.sh` is the local and CI entry point. Its architecture
stage, `scripts/quality-gate.sh`, runs:

- Ruff lint, import ordering, complexity, unused-code, and format checks on the
  incrementally protected architecture surface;
- strict mypy checks on ports and composition roots (the Dash UI is Python, so
  this is also the frontend type boundary);
- architecture dependency and circular-import checks;
- exact structural duplication detection for protected modules.

The release gate then runs the complete pytest suite, including reusable adapter
contract tests, plus dependency, import, JavaScript syntax, SCSS compilation,
and diff-integrity checks.

The protected surface expands as Issue 077 migrates legacy modules. Existing
legacy coupling is not permission to add another violation.

## Pull-request SOLID review

For each changed unit, verify responsibility, extension point, substitutability,
interface width, dependency direction, error/null/unit/freshness semantics,
duplication, test boundary, and whether the abstraction is simpler than the
coupling it replaces. The repository pull-request template records this review.

## Exceptions

Exceptions are temporary and must be recorded in
`docs/architecture-exceptions.md` before merge. An exception requires scope,
risk, owner, reason, containment, removal trigger, and target issue/date. It may
not weaken a financial invariant, silently change units, or expose a vendor
payload to domain code. New CI suppressions must name the exception record.
