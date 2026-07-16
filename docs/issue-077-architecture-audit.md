# Issue 077 Repository Architecture and SOLID Audit

## Scope and method

This audit covers every Python module under `codes`, every test, JavaScript and
SCSS source, CI workflow, worker, route, and script in the repository. The
machine-readable companion is generated with:

```bash
python scripts/architecture-report.py --check --output /tmp/architecture-report.json
ruff check codes --statistics
mypy codes --follow-imports=skip --no-error-summary
APP_SKIP_STARTUP=1 python -c "import codes.app"
```

The report uses AST-derived file/function size, decision complexity, parameter
counts, boolean flags, imports, cycles, exact duplicate function bodies, mutable
module globals, environment reads, inline style dictionaries, Git change
frequency, and active exception records. Measurements rank risk; they are not
automatic reasons to split cohesive code.

## Pre-migration baseline

Captured before the Issue 077 reference slices:

| Measure | Baseline |
|---|---:|
| Python source lines | 30,492 |
| Full tests | 1,057 passed, 2 skipped |
| Ruff findings across `codes` | 182 |
| Strict whole-tree mypy findings | 1,076 |
| Critical-layer import cycles | 0 |
| Active architecture exceptions | 3 |
| Direct HTTP clients in engine/domain allowlist | 1 (`engine/universe.py`) |
| Presentation modules importing calculation models | 1 (`app_modules/analysis.py`) |
| Application services importing Flask/Dash | 1 (`services/product_analytics.py`) |
| Import with startup disabled | 1.19 seconds |
| Release gate wall time | approximately 26 seconds before coverage instrumentation |

Coverage by critical package is emitted as `/tmp/coverage.json` by the release
gate and uploaded with the architecture report. The final migration result is
recorded below.

## Post-migration verified baseline

| Measure | Result |
|---|---:|
| Full tests | 1,062 passed, 2 skipped |
| Total statement coverage | 68% (8,651 / 12,782) |
| Financial models coverage | 82.0% |
| Portfolio coverage | 85.6% |
| Data-layer coverage | 59.0% |
| Application-services coverage | 64.0% |
| Engine coverage | 54.8% |
| Presentation package coverage | 57.5% |
| Critical-layer import cycles | 0 |
| Active architecture exceptions | 0 |
| Domain-to-infrastructure imports | 0 |
| Presentation-to-calculation imports | 0 |
| Service-to-framework imports | 0 |
| Python source files / lines | 124 / 30,715 |
| Exact duplicate function groups remaining | 8 (registered debt) |

The release gate, dependency audit, protected Ruff/strict-mypy checks, JS/SCSS
checks, architecture report, golden suite, coverage capture, and diff integrity
all pass. The Sass compiler emits one existing mixed-declarations deprecation
warning; tracked CSS remains exactly reproducible.

## Current architecture map

```text
Flask routes / Dash tabs / UI builders
  -> application services and engines
     -> pure financial models and contracts
     -> narrow ports
  <- infrastructure adapters (SEC/provider, Postgres, Redis, cache)

Composition roots:
  codes.composition.compose_runtime
  codes.app_modules.composition.compose_dash_ui
```

The stock-analysis workflow now lives in `codes.services.stock_analysis`; Dash
only invokes the application service and renders its result. SEC ticker payloads
are normalized by `SecTickerUniverseAdapter` before entering the engine.
Product analytics receives an `AnalyticsContext` adapter configured by the Dash
composition root, so the service does not import Flask.

## Repository-wide findings

### Financial calculations and score integrity

- Financial models are framework-neutral and have extensive focused tests.
- The main risk is size rather than dependency direction: Buffett `score` is
  455 lines/complexity 117, Graham `score` is 324/78, and Piotroski `score` is
  186/73. Refactor only behind golden fixtures; do not mix formula changes with
  decomposition.
- `enhanced_composite` has 14 parameters and complexity 47. Its weights and
  fallback semantics are financially sensitive and now have an Issue 077 golden
  fixture in addition to existing model tests.

### Providers, normalization, validation, and retries

- Provider implementations are correctly concentrated under `codes.data` and
  `codes.data.providers`, but `api_fetcher.py` (1,086 lines) and `sec_data.py`
  (1,165 lines) combine client, retry/cache, mapping, and domain preparation.
- The SEC universe slice previously leaked HTTP and raw payload handling into
  `codes.engine.universe`; this is resolved behind `TickerUniverseReader`.
- Canada has explicit canonical normalization and provider contract tests. New
  providers must use the same adapter/contract pattern.

### Persistence and transactions

- `codes/data/db.py` is the largest module at 2,020 lines and owns unrelated
  market, user, screener, analysis, snapshot, and migration concerns.
- Database access is concentrated in data modules and application services, but
  repository interfaces are inconsistent and transaction ownership is often
  implicit. Split by consumer capability, beginning with analysis snapshots and
  user portfolios.

### Application orchestration and background work

- `stock_analysis.py` remains a 594-line orchestration hotspot (complexity 75)
  with provider, calculation, persistence, cache, and secondary-job steps. Its
  presentation coupling is removed, but later slices should introduce focused
  input, persistence, and secondary-analysis collaborators.
- Workers reuse the stock-analysis service rather than duplicating calculations.
- Module caches and executors are mutable globals; 68 mutable module-level
  collections exist across the tree. They require targeted injection only where
  concurrency or deterministic testing is at risk.

### Authentication, permissions, subscriptions, and capabilities

- Capability checks are centralized in `codes.services.permissions`; payment
  adapters are separated under `codes.payments`.
- Product analytics previously mixed session/framework access with event policy.
  That backend reference slice is resolved through `AnalyticsContext`.
- Future entitlement work must eliminate remaining plan-name conditionals at
  callers rather than add another parallel permission path.

### Routes, presentation, and UI state

- `analysis_ui.py` (1,674 lines), screener tab (870), and portfolio tab (819)
  are the largest UI units. `analysis_ui._build_analysis_content` is 435 lines
  with complexity 57; screener rendering is 286/62.
- Exact duplicate `_fmt` helpers are present in analysis UI. Consolidate them
  into the Issue 075 design engine when that dependency is available.
- No migrated presentation module imports calculation models. There are zero
  raw inline Dash style dictionaries by the report's strict pattern; SCSS is
  centralized but several partials remain large.
- Analyze and Portfolio currently consume shared tokens/partials. Their full
  component migration is blocked on Issue 075 and is registered as planned debt,
  not an architecture exception permitting new page-specific styles.

### Cycles, hidden dependencies, flags, and dead/duplicate code

- No import cycle was found, including critical domain paths.
- The current report finds 100 environment reads, 68 mutable module globals, 23
  functions with boolean defaults, and 8 exact duplicate function-body groups.
- Whole-tree Ruff reports unused imports/variables, import ordering, complexity,
  and one undefined name among its 182 legacy findings. Protected migrated files
  are clean and strictly typed; the protected set expands per migration slice.
- No inheritance hierarchy was found that warrants a migration framework.

## Risk ranking

Ranking combines business criticality, complexity, coupling, coverage, and Git
change frequency. `codes/app.py` is touched by 121 commits; analysis UI 28; DB
and screener tab 25 each; screener engine 21; routes/layout 20; portfolio 17;
API fetcher 15; analyze tab 14; scorer 13.

1. Critical: financial golden boundaries and stock-analysis orchestration.
2. Critical: database repository/transaction decomposition.
3. High: SEC/API provider client-normalization separation.
4. High: Analyze UI content builder and duplicated formatters.
5. High: Portfolio and Screener callback/view-model separation.
6. Medium: strict typing and Ruff expansion through touched modules.
7. Medium: mutable caches, environment reads, boolean flag APIs.
8. Low: large but stable supporting SCSS/scripts with no boundary violation.

Detailed ownership and triggers are in `docs/technical-debt-register.md`.

## Reference migrations completed

- Backend: product analytics policy is framework-neutral and receives a narrow
  Flask adapter at the presentation composition root.
- Data provider: SEC universe HTTP/payload mapping moved behind a typed adapter
  with normalization and substitution tests.
- Frontend workflow: stock-analysis calculation/orchestration moved out of the
  Dash presentation package into an application service; all UI, worker,
  scheduler, and tests use the stable service boundary.
- Financial safety: pre-migration composite and math outputs are frozen in a
  golden fixture; the full existing regression suite remains authoritative.

## Current enforcement and dashboard

CI runs Ruff formatting/lint/complexity/unused checks on protected files, strict
mypy on typed boundaries, architecture and duplication gates, the generated
repository report, dependency audit, JS/SCSS checks, coverage, and the full test
suite. It uploads `architecture-report.json` and `coverage.json`. CI fails if a
critical cycle, domain-infrastructure import, presentation-domain import,
service-framework import, or undocumented active exception appears.
