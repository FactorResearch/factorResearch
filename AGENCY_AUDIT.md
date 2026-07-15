# FactorResearch Full-Agency Application Audit

**Audit date:** 2026-07-14
**Branch:** `optimization`
**Scope:** Product, UX/UI, accessibility, frontend, backend, data, quantitative models, performance, security, privacy, testing, DevOps, observability, and developer experience.

## Executive Summary

FactorResearch has a strong product direction, unusually broad model coverage, explicit performance goals, and substantial regression-test investment. The primary risk is no longer lack of features. It is **operational coherence**: tests, architecture, styling, security controls, and release automation have evolved at different speeds.

The highest-value next step is a stabilization release before adding more models. The full test suite currently reports **95 failures, 982 passes, and 2 skips**. Many failures appear to be stale contracts after refactors rather than confirmed production defects, but that distinction cannot be trusted until the suite is reconciled. CI currently runs only a narrow subset, so a pull request can be green while the repository-wide suite is red.

The application should prioritize:

1. Restore a trustworthy full-suite release gate.
2. Consolidate UI styling and remove runtime patch layers.
3. Enforce architectural boundaries around providers, models, persistence, and UI composition.
4. Complete production security, privacy, monitoring, and recovery controls.
5. Validate real populated workflows, not only empty/static shells.

## Audit Evidence

| Check | Result |
|---|---|
| Python compilation | Pass |
| SCSS compilation | Pass |
| `git diff --check` | Pass before report creation |
| Full Pytest suite | **95 failed, 982 passed, 2 skipped** |
| Axe: desktop, tablet, mobile | 0 automated violations across Screener, Analyze, Portfolio shells |
| npm vulnerability audit | 0 known vulnerabilities |
| Python vulnerability audit | Not run locally; `pip-audit` is not installed. Weekly CI workflow exists. |
| Python application size | Approximately 29,494 lines |
| Test code size | Approximately 14,120 lines |
| Largest Python modules | `analysis_ui.py` 74 KB, `db.py` 69 KB, portfolio tab 50 KB, `sec_data.py` 45 KB, `api_fetcher.py` 41 KB |
| Styling debt indicators | 278 `!important` declarations, multiple generated/patch CSS files, 3 remaining inline styles |

## Priority 0: Restore Release Confidence

### 1. Reconcile the full test suite

**Problem:** The full suite has 95 failures while PR CI executes only a small selected group. Failure clusters include removed or moved portfolio comparison helpers, stale screener pagination assumptions, changed portfolio function signatures, old SEC/FMP cache behavior, CSS string assertions, and shared-state leakage.

**Improvements:**

- Classify every failure as product regression, stale test, environment leak, or obsolete feature.
- Repair product regressions first; update or delete tests only when the intended contract is documented.
- Isolate environment variables, module-level caches, database adapters, and imported singleton state between tests.
- Replace CSS substring assertions with rendered behavior, visual regression, or semantic DOM assertions.
- Add a temporary `known_failure` manifest only if each entry has an owner and expiry date.
- Make the complete stable suite mandatory on every pull request; move only genuinely slow integration suites to a second required job.

**Acceptance:** Main is green with no unexplained skips or xfails, and a deliberately introduced regression fails CI.

### 2. Separate unit, integration, contract, UI, and live-provider tests

**Problem:** The suite mixes implementation-shape tests, network-adapter contracts, Dash callback behavior, UI string checks, and model math. This makes refactors noisy and hides meaningful failures.

**Improvements:**

- Add Pytest markers and directories for `unit`, `integration`, `contract`, `ui`, `security`, `performance`, and `live_provider`.
- Ban live network access in the default suite using an autouse fixture.
- Provide deterministic provider fixtures captured with provenance and dates.
- Test public contracts rather than private helper locations.
- Publish duration, flake rate, and coverage trends in CI.

### 3. Establish a release definition of done

- Full required test matrix passes.
- SCSS and generated assets are reproducible with no diff.
- Python and npm vulnerability scans pass.
- Accessibility and keyboard smoke suites pass on populated states.
- Database migration and rollback are tested.
- Performance budgets show no material regression.
- Security/privacy checklist is reviewed for the release.

## Product and Information Architecture

### 4. Define a progressive-disclosure contract

The current direction is correct: users should understand a stock quickly and request depth only when needed. Formalize three levels:

- **Glance:** verdict, composite score, price, market cap, moat, freshness, and material warning.
- **Understand:** concise factor highlights, accounting risk, trend, and evidence quality.
- **Investigate:** expanded charts, model inputs, filings, methodology, and historical detail.

Every new model must declare which level exposes it. This prevents future card accumulation and protects the quick-analysis use case.

### 5. Create a model-to-surface registry

**Problem:** Engines and UI cards can diverge, resulting in computations with no visible output or cards without clear data provenance.

Create one registry containing:

- Model ID, version, owner, status, and feature flag.
- Required inputs and data freshness.
- Server cost and cache policy.
- UI surface and progressive-disclosure level.
- Existing-stock backfill strategy.
- Empty, partial-data, stale-data, and failure behavior.
- Methodology and interpretation link.

Add a test that fails when a production engine has no declared UI/API consumer unless it is explicitly marked background-only.

### 6. Improve trust communication

- Show data freshness and source coverage without turning them into dominant cards.
- Distinguish unavailable, not applicable, stale, and failed calculations.
- Explain score movement when the composite changes materially.
- Expose model version and methodology from detail views.
- Avoid authoritative language where data coverage is incomplete.

## UX, Visual Design, and Accessibility

### 7. Consolidate the design system

**Problem:** Styling remains split across SCSS partials, standalone SCSS/CSS, generated CSS, and several `zz_*` patch files. There are 278 `!important` declarations. This creates cascade uncertainty and recurring light/dark/mobile regressions.

**Improvements:**

- Define a single layer order: reset, tokens, base, components, layouts, utilities, responsive overrides.
- Replace `zz_runtime_fixes.css` and other `zz_*` files by moving rules into owned SCSS components, then delete the patches.
- Adopt semantic tokens for surfaces, text, borders, status, charts, focus, and disabled states.
- Keep component selectors shallow and scoped; use `!important` only for documented third-party overrides.
- Generate all deployable CSS from one command and verify reproducibility in CI.
- Resolve remaining inline `style` properties with semantic state classes or hidden attributes.

### 8. Extend accessibility beyond automated axe checks

The shell audit passed at 1440x1000, 820x1180, and 390x844. It covered Screener, Analyze, and Portfolio, but primarily empty/mock states.

Add coverage for:

- Populated screener rows, Quick Peek, accordions, charts, legal dialogs, pricing locks, errors, loading, and portfolio simulation.
- Full keyboard-only navigation, visible focus, focus restoration, Escape behavior, and no focus trapping behind overlays.
- Screen-reader announcements for analysis completion, errors, sorting, filtering, chart expansion, and updated results.
- A skip link and stable heading hierarchy.
- Reduced motion, 200% text zoom, 400% reflow, high contrast, and forced-colors mode.
- Chart data tables or equivalent text summaries.
- Touch targets of at least 44x44 CSS pixels for primary mobile actions.
- Contrast validation for every semantic token in light and dark themes.

### 9. Add visual regression testing

- Capture key populated states in light and dark themes at desktop, tablet, and mobile widths.
- Include Quick Peek open/closed, long company names, missing logos, long numbers, errors, and partial model data.
- Use stable fixtures and mask only truly dynamic timestamps.
- Require review for intentional baseline changes.

### 10. Improve perceived-native behavior carefully

- Use route-aware skeletons with fixed dimensions to prevent layout shift.
- Preserve tab, filter, expanded section, and scroll state without surprising jumps.
- Prefetch only likely next interactions; do not precompute every chart.
- Add offline/error recovery messaging rather than pretending the analytical product works offline.
- Version service-worker caches from the build identifier and remove old caches on activation.
- Do not force a page reload from hard-coded JavaScript app versions; use asset fingerprinting and controlled update prompts.

## Frontend Engineering

### 11. Reduce Dash callback and DOM coupling

- Group callbacks by feature boundary with explicit input/output contracts.
- Replace broad callback exception suppression with validation layouts where practical.
- Minimize callbacks that return large component trees; return data and render stable client structures when safe.
- Use pattern-matching IDs consistently and document ownership.
- Add callback graph tests for duplicate outputs, circular dependencies, and orphan components.
- Report callback duration and payload size by callback ID.

### 12. Treat charts as optional heavy resources

- Keep chart history out of initial analysis payloads.
- Fetch and render only after explicit expansion.
- Give every graph stable responsive bounds and a text fallback.
- Cache normalized series rather than serialized presentation objects when it improves reuse.
- Downsample long series according to viewport and preserve exact values for accessible tables/tooltips.
- Cancel or ignore stale chart requests after ticker/tab changes.

### 13. Improve frontend asset delivery

- Fingerprint CSS/JS assets and use immutable cache headers.
- Minify production assets in the release pipeline.
- Audit which CSS files Dash injects and enforce the intended list in a test.
- Add bundle/asset-size budgets.
- Move large inline scripts from `app.index_string` into versioned, testable JS modules.

## Backend and Architecture

### 14. Break up change-risk hotspots

Large modules currently combine multiple responsibilities. Prioritize decomposition of:

- `codes/app_modules/analysis_ui.py`
- `codes/data/db.py`
- `codes/app_modules/tabs/portfolio.py`
- `codes/data/sec_data.py`
- `codes/data/api_fetcher.py`
- `codes/app_modules/tabs/screener.py`
- `codes/portfolio.py`

Split by stable domain boundaries, not arbitrary line count. Preserve public facades during migration to avoid another test-contract cascade.

### 15. Enforce provider boundaries

The architecture document says business logic must not call vendors directly, but direct `requests` usage remains in SEC, universe, auth, and fetcher paths. Auth and low-level adapters are reasonable exceptions; market/business access should go through canonical providers.

- Define typed provider protocols and canonical response objects.
- Make retry, timeout, rate limit, circuit breaker, telemetry, and error translation shared middleware.
- Prohibit direct market-provider HTTP calls outside adapter packages with an architecture test.
- Preserve raw source provenance and observation timestamps.

### 16. Adopt typed domain contracts

- Replace loosely shaped dictionaries at module boundaries with dataclasses, TypedDicts, or validation models.
- Represent missing data explicitly rather than overloading `None`, zero, empty strings, and absent keys.
- Version analysis snapshots and migrations.
- Add result equivalence tests for optimization work.
- Use one canonical money, percentage, date, and fiscal-period representation.

### 17. Remove silent exception paths

The codebase contains many broad `except Exception` handlers. Some are valid resilience boundaries, but silent fallbacks can transform provider or model failures into believable empty results.

- Catch narrow exceptions inside models and adapters.
- At resilience boundaries, log structured context, increment a metric, and return a typed degraded result.
- Never treat failure as valid zero unless the model contract explicitly permits it.
- Add fault-injection tests for timeout, malformed payload, partial filing, stale cache, Redis outage, and database outage.

## Data and Quantitative Integrity

### 18. Add data lineage and quality scoring

- Store provider, filing/accession, period, retrieval time, normalization version, and confidence for each derived input.
- Validate units, currencies, split adjustments, fiscal calendars, duplicate periods, restatements, and impossible signs/ranges.
- Surface a compact evidence-quality indicator when confidence affects interpretation.
- Quarantine anomalous records instead of silently scoring them.

### 19. Create golden model fixtures

For every production model:

- Maintain hand-reviewed fixtures covering healthy, distressed, manipulated, sparse, restated, financial-sector, and non-US companies where applicable.
- Validate intermediate values, not only final scores.
- Test mathematical invariants and monotonic expectations.
- Compare outputs before and after optimization or provider changes.
- Record model version in every stored analysis.

### 20. Formalize backfill and recomputation policy

Every new model must work for already analyzed database stocks. Enforce this through:

- A migration/backfill plan in the model registry.
- Idempotent, resumable, rate-limited jobs.
- Priority based on user demand and stale/missing components.
- Component-level invalidation rather than full-analysis recomputation.
- Progress, failure, retry, and dead-letter visibility.

### 21. Guard against investment-analysis bias

- Document survivorship, look-ahead, restatement, and availability-date assumptions.
- Separate point-in-time backtest data from latest-known analysis data.
- Include fees, slippage, liquidity, corporate actions, and delistings where relevant.
- Report uncertainty and sample size alongside performance.
- Require benchmark and methodology review before presenting backtest claims publicly.

## Performance and Scalability

### 22. Turn performance targets into enforced budgets

`docs/PERFORMANCE.md` defines useful p50/p95 goals, but CI does not enforce them.

- Add deterministic benchmarks for cached analysis, Quick Peek, callback serialization, chart expansion, and model components.
- Add load tests for concurrent popular and cold tickers.
- Track response size, callback payload, DB queries, provider calls, cache hit rate, and layout shift.
- Fail or warn when budgets regress beyond an agreed tolerance.

### 23. Make cache behavior observable and safe

- Document cache keys, ownership, TTL, invalidation, encryption, and stale-while-revalidate behavior.
- Include model/data/schema versions in keys.
- Prevent cache stampedes across workers and verify single-flight under failure.
- Bound in-memory caches and expose eviction metrics.
- Test Redis outage behavior without silently removing production rate limits.

### 24. Move durable work out of web startup

Schema initialization and application warm-up currently occur during import/startup paths. Production should use:

- Explicit database migrations before deploy.
- Dedicated worker processes for backfills and secondary analysis.
- Readiness checks that verify required dependencies without performing durable mutations.
- Liveness checks that do not call vendors.
- Graceful shutdown and job visibility.

## Security and Privacy

### 25. Harden HTTP security policy

Existing strengths include secure production secret requirements, same-origin mutation checks, security headers, encrypted sensitive cache kinds, Stripe signature verification, and output sanitization.

Remaining improvements:

- Add a nonce- or hash-based Content Security Policy and remove inline scripts over time.
- Add `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`, and an explicit frame policy where compatible.
- Replace `Access-Control-Allow-Origin: none` with omission of CORS headers until a real allow-list is needed.
- Validate trusted proxy configuration and allowed hosts in production.
- Ensure external redirects and generated absolute URLs use configured origins, not untrusted Host headers.
- Add security tests for every state-changing Flask route, including account deletion and analytics preference changes.

### 26. Resolve session and rate-limit configuration ambiguity

`security.py` configures a 24-hour lifetime, while `auth.py` configures 30 days and determines secure-cookie mode partly from `app.debug`. Flask-Limiter also warns that it uses in-memory storage in the audited runtime.

- Define session policy once from explicit environment configuration.
- Use Redis-backed Flask-Limiter storage in production and fail closed if required infrastructure is missing.
- Add per-account and per-IP limits for login, analysis, logo proxying, portfolio mutation, and expensive routes.
- Test multi-worker enforcement and proxy-aware client identification.

### 27. Add security automation

- Run full Python dependency scanning on pull requests and scheduled builds.
- Add secret scanning, SAST, and dependency-update automation.
- Generate an SBOM and retain build provenance.
- Pin all direct dependencies exactly or use a locked constraints file; `dash_svg` and Stripe currently use ranges.
- Add security review for provider payload parsing and SVG/image handling.
- Perform an external penetration test before broad public launch.

### 28. Finish privacy and compliance work

- Replace placeholder legal content with counsel-reviewed Terms and Privacy Policy.
- Maintain a data inventory, retention schedule, subprocessors list, and deletion verification procedure.
- Ensure analytics opt-out prevents collection before events are emitted.
- Define cookie consent requirements by target jurisdiction.
- Test account export and deletion across PostgreSQL, Redis, logs, backups, billing, and analytics systems.
- Establish incident response contacts, breach notification workflow, and evidence retention.

## Reliability, Observability, and Operations

### 29. Add production-grade telemetry

- Structured JSON logs with request ID, user-safe actor ID, ticker, provider, model version, latency, and outcome.
- Distributed traces across callback, cache, DB, provider, and worker boundaries.
- Metrics for latency, errors, saturation, queue age, stale analysis, cache hit rate, provider budgets, and model failures.
- Client-side error and Web Vitals reporting with privacy controls.
- Dashboards and alerts tied to service objectives, not raw infrastructure noise.

### 30. Improve deployment safety

- Replace the minimal Procfile-only contract with documented web/worker/release process definitions.
- Configure Gunicorn workers, threads, timeout, graceful timeout, max requests, and preload behavior based on measurement.
- Add staged migrations, canary rollout, health checks, and automatic rollback criteria.
- Verify environment configuration at startup with actionable errors.
- Keep dev, staging, and production behavior aligned while preventing production data access from test environments.

### 31. Build tested backup and disaster recovery

- Encrypt database and object backups.
- Run automated restore drills into isolated environments.
- Define and measure recovery point and recovery time objectives.
- Back up configuration and migration metadata, not secrets in source control.
- Document provider-outage and database-failover runbooks.

## Developer Experience and Governance

### 32. Remove repository debris and clarify generated files

- Remove or resolve tracked `codes/portfolio.py.rej`.
- Define whether compiled CSS is source-controlled; avoid mixed rules where some generated CSS is ignored and patch CSS is tracked.
- Add one bootstrap command and one comprehensive validation command.
- Add pre-commit checks for formatting, linting, architecture boundaries, secrets, SCSS, and fast tests.

### 33. Add static quality gates

- Adopt a formatter and linter for Python and JavaScript.
- Add gradual type checking at domain/provider boundaries first.
- Enforce import layering and prevent circular dependencies.
- Track complexity and module growth as advisory metrics.
- Require docstrings only for public contracts and non-obvious model assumptions, not boilerplate.

### 34. Keep documentation executable

- Link architecture decisions to tests and code owners.
- Add architecture decision records for caching, provider routing, snapshots, auth, and progressive disclosure.
- Generate model inventory and route/callback inventory from code.
- Mark checklist items with evidence links and re-audit dates.
- Remove stale issue documentation after its requirements become permanent tests or architecture rules.

## Recommended Delivery Plan

### Phase 1: Stabilize (1-2 weeks)

- Reconcile all 95 test failures.
- Make the full stable suite required in CI.
- Remove the rejected patch file and identify generated asset ownership.
- Fix session/rate-limit configuration ambiguity.
- Add populated-state keyboard and accessibility smoke tests.
- Establish baseline performance and payload measurements.

### Phase 2: Consolidate (2-4 weeks)

- Consolidate SCSS and eliminate `zz_*` patches incrementally.
- Introduce model registry, typed results, and architecture tests.
- Decompose the largest UI/data modules behind stable facades.
- Add structured errors, telemetry, and provider middleware.
- Introduce explicit migrations and dedicated worker deployment.

### Phase 3: Operationalize (3-6 weeks)

- Add load tests, visual regression, SAST, secret scanning, SBOM, and full dependency automation.
- Build dashboards, alerts, tracing, and recovery runbooks.
- Complete legal/privacy review and deletion/export verification.
- Run restore drills and an external penetration test.

### Phase 4: Scale Product Safely (ongoing)

- Add models only through the registry and backfill contract.
- Enforce progressive disclosure and initial-payload budgets.
- Use demand-prioritized background computation.
- Require golden-fixture and point-in-time integrity checks for every model release.
- Review product comprehension, task completion time, and trust signals with real users.

## Suggested Success Metrics

| Area | Target |
|---|---|
| Release quality | 100% required CI pass; <1% flaky-test rate |
| Cached analysis | p95 <= 300 ms |
| Quick Peek | p95 <= 200 ms |
| Fresh primary analysis | p95 <= 3 s |
| Chart expansion | p95 <= 750 ms |
| Initial analysis payload | <= 64 KB |
| Runtime errors | <0.5% requests/callbacks |
| Accessibility | 0 critical/serious automated violations plus keyboard and screen-reader sign-off |
| Layout stability | Core Web Vitals CLS <= 0.1 |
| Security | No unresolved critical/high known vulnerabilities |
| Recovery | Documented and tested RPO/RTO |
| Model integrity | 100% production models registered, versioned, surfaced, and backfill-capable |

## Final Assessment

The application does not need indiscriminate feature reduction. It needs stronger contracts around what is computed, when it is computed, how it is presented, and how correctness is proven. The fastest path to a premium, native-feeling product is to make the existing system predictable: stable tests, progressive disclosure, coherent styling, typed model/data boundaries, observable asynchronous work, and production-grade operational controls.
