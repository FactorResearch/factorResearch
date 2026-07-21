# Cenvarn — AI Engineering Instructions

## 1. Authority and scope

This file is the mandatory entry point for every AI coding task in this repository.

These instructions apply to all files under this directory unless a more specific nested `AI_WORKFLOW.md` exists. A nested file may add stricter local rules but must not weaken repository-wide safety, security, testing, documentation, financial correctness, data integrity, paper-first design, or no-reinvention requirements.

Notion contains the full engineering standards. This file defines the startup sequence, minimum rules, routing requirements, and completion gates that always apply.

When the user says `Run ISSUE_046`, the AI open `AI_WORKFLOW.md` and read from there.

`AI_CONTEXT.md` contains repository-specific product memory, Ponytail simplicity rules, financial-model conventions, design constraints, and current architectural context. It is mandatory reading for every non-trivial task and must never be silently replaced by a generic agent template.

Do not rely on memory from previous conversations or coding sessions. Reload the current repository instructions and applicable standards for every task.

When instructions conflict, use this priority order:

1. Security, privacy, authorization, and prevention of data loss or cross-user access.
2. Mathematical and financial-model correctness.
3. Reproducibility, provenance, point-in-time integrity, and backward compatibility.
4. Accessibility and successful completion of the user task.
5. Test evidence and operational reliability.
6. Performance and resource efficiency.
7. Simplicity and maintainability.
8. Visual polish.

Shorter code is preferred only when every higher priority remains protected.

## 2. Repository documentation layout

Repository standards:

- `docs/engineering.md`
- `docs/frontend.md`
- `docs/api.md`
- `docs/database.md`
- `docs/testing.md`
- `docs/security.md`
- `docs/log.md`
- `docs/workers.md`
- `docs/caching.md`
- `docs/financial.md`
- `docs/data-providers.md`
- `docs/config.md`
- `docs/dependency.md`
- `docs/release.md`
- `docs/accessibility.md`
- `docs/git.md`
- `docs/ui.md`

Always load documents using actual repository paths. Do not invent names from memory.

## 3. Mandatory startup sequence

Before writing or modifying code:

1. Read this entire file.
2. Read `AI_CONTEXT.md` for every non-trivial task.
3. Read the issue, specification, design reference, acceptance criteria, and linked decisions.
4. Inspect the affected files, callers, tests, persistence, contracts, and nearby implementations.
5. Reproduce the problem or otherwise prove the requested gap exists.
6. Check the worktree and preserve unrelated user changes.
7. Identify every architectural layer and user-visible behavior affected.
8. Load the mandatory core standards.
9. Load every applicable specialist standard from the routing matrix.
10. Search for existing functions, services, components, schemas, utilities, native platform features, and approved dependencies that may already solve the problem.
11. Complete the written engineering design gate described below.
12. Define behavior, boundaries, failure modes, invariants, tests, observability, migration, and rollback before implementation.
13. Make the smallest complete change that satisfies the approved written solution.
14. Run focused validation first, then the complete applicable release gate.
15. Reinspect the diff against the issue and written design before declaring completion.

Do not begin implementation while required standards, repository context, or the written solution are missing.

## 4. Mandatory core standards

Load and apply these standards for every coding task:

- Engineering Code Standards.
- Applicable Python Engineering Standards.
- Applicable JavaScript and TypeScript Engineering Standards.
- Testing Engineering Standards.
- Security Engineering Standards.
- Git and Pull Request Standards.
- AI Standards Loading and Task Routing Policy.
- Build-vs-Buy and No-Reinvention Policy.
- `AI_CONTEXT.md` Ponytail and repository-specific rules.

A task touching multiple languages or layers must load the standards for every affected area.

## 5. Specialist standards routing matrix

| Task area | Required specialist standards |
|---|---|
| UI, layout, component, SCSS, theme, responsive behavior | New UI Design Implementation Plan; Accessibility Engineering Standards; Performance Engineering Standards when rendering or bundle cost may change |
| API endpoint, request, response, contract, authentication boundary | API Engineering Standards; Observability and Logging Standards |
| Database schema, query, repository, transaction, migration | Database Engineering Standards; Release and Incident Standards for migrations |
| Financial formula, score, valuation, backtest, benchmark, portfolio calculation | Financial Calculation Standards; Database Engineering Standards when persisted; Testing Engineering Standards |
| External market, filing, quote, or fundamental data | Data Provider Engineering Standards; Caching Engineering Standards when cached; Observability and Logging Standards |
| Worker, scheduled task, queue, batch, refresh process | Background Jobs and Worker Standards; Observability and Logging Standards; Configuration and Environment Standards |
| Cache, memoization, stale data, invalidation | Caching Engineering Standards; Data Provider Engineering Standards where external data is involved |
| Configuration, environment variables, feature flags, secrets | Configuration and Environment Standards; Security Engineering Standards |
| New or upgraded package | Dependency and Package Standards; Security Engineering Standards; Build-vs-Buy and No-Reinvention Policy |
| Performance-sensitive or native-code path | Performance Engineering Standards; Observability and Logging Standards; Rust migration rules in this file |
| Deployment, schema rollout, production migration, incident remediation | Release and Incident Standards; Observability and Logging Standards |
| Cross-cutting feature | Load all standards for every affected layer |

Do not load every full specialist standard for an unrelated one-line change. Load the mandatory core set plus every standard relevant to the actual impact.

## 6. Paper-first issue resolution

Every non-trivial issue must be solved in writing before it is solved in code.

The written solution may live in the issue, an approved design document, an ADR, or a checked-in implementation note. It must be concrete enough that another engineer could review the intended behavior before seeing the implementation.

The written solution must define:

1. The requested user-visible outcome.
2. The verified current behavior and root cause.
3. The exact scope and explicit non-goals.
4. Existing code, platform features, or dependencies that will be reused.
5. The proposed ownership and architectural boundary.
6. Public contracts and persisted data affected.
7. Inputs, outputs, units, nullability, ordering, freshness, and error behavior.
8. Failure modes, degraded behavior, retries, idempotency, concurrency, cancellation, and restart behavior.
9. Security, privacy, authorization, and tenant-isolation implications.
10. Financial-methodology and point-in-time implications.
11. Performance and resource implications.
12. Observability and alerting requirements.
13. Test plan and acceptance evidence.
14. Migration, rollout, compatibility, and rollback plan.
15. Why the solution is the smallest complete option.

The written solution must be updated when implementation discoveries materially change the design. Code must not quietly diverge from the approved paper solution.

A task is not complete merely because code exists. The issue must contain or link to the final reconciled design and observed verification evidence.

## 7. Engineering design gate

Before implementation, answer these questions in writing:

1. What is the actual problem rather than the visible symptom?
2. Does this behavior need to exist?
3. Does the repository already solve it?
4. Can an existing helper or approved abstraction solve it?
5. Can the standard library solve it?
6. Can PostgreSQL solve it safely and clearly?
7. Can the browser, CSS, framework, operating system, CDN, or platform solve it natively?
8. Can an already-approved dependency solve it?
9. Can direct readable code solve it without a new abstraction?
10. Is Rust justified by production-shaped evidence, or would the language boundary cost more than the work?
11. Should the correct implementation be deletion or no code at all?

Implementation starts only after the first defensible rung that fully solves the problem is selected.

## 8. Ponytail simplicity standard

Be a lazy senior engineer: efficient, not careless. The best code is code that does not need to exist.

Use this order:

1. Skip speculative work.
2. Reuse the repository's existing implementation.
3. Use the standard library.
4. Use browser, database, framework, CSS, HTTP, operating-system, or platform-native behavior.
5. Use an already-installed approved dependency.
6. Use direct, readable code without a new abstraction.
7. Only then add the minimum new implementation.

Rules:

- Root-cause fixes beat symptom patches.
- One shared guard at the correct boundary is better than repeated guards in callers.
- Delete dead behavior before adding replacement layers.
- Prefer boring explicit code over clever compression.
- Use the fewest files and concepts that preserve clear ownership.
- Do not add interfaces with one implementation, factories with one product, wrappers that only delegate, configuration nobody changes, speculative extension points, or dependencies for a few clear lines.
- Do not split large files merely to reduce line count. Split when ownership, behavior, change cadence, or test boundaries become clearer.
- Consolidate only truly identical financial behavior. Do not merge formulas with different thresholds, accepted records, missing-data semantics, or output meaning.
- No speculative refactoring. Refactor only when requested or when it is the smallest safe path to the required result.
- Mark a deliberate shortcut only with `ponytail: <ceiling>, <specific trigger or upgrade path>`.

Over-engineering review labels:

- `delete`: remove dead or speculative behavior and replace it with nothing.
- `stdlib`: replace custom code with the named standard-library feature.
- `native`: replace code or dependency with a platform-native feature.
- `yagni`: remove unused flexibility or abstraction.
- `shrink`: preserve behavior with materially simpler readable code.

Complexity findings are separate from correctness, security, accessibility, and performance findings. Never delete a protective control merely to simplify code.

## 9. Documentation-first implementation workflow

For every new or modified non-trivial class, function, method, hook, component, service, repository, provider, worker, query, financial calculation, Rust kernel, or public type:

1. Write or update its documentation and contract before implementation.
2. Define responsibility and why the unit exists.
3. Define what it owns and what it must never own.
4. Define inputs, outputs, types, units, nullability, ordering, currency, time zone, and freshness.
5. Define side effects and external dependencies.
6. Define errors, failure modes, degraded behavior, retries, idempotency, concurrency, cancellation, and restart expectations.
7. Define assumptions, invariants, preconditions, postconditions, and edge cases.
8. Define performance expectations and memory or payload limits where relevant.
9. Confirm it does not duplicate an existing abstraction.
10. Define tests before implementation.
11. Implement only the documented behavior.
12. Reconcile documentation, types, code, tests, and the issue before completion.

Do not write a large implementation first and add comments afterward.

### 9.1 Class contract requirement

Every non-trivial class must document:

- Purpose and domain responsibility.
- Why a class is appropriate instead of a function or data structure.
- Ownership and lifecycle.
- Constructor inputs and validation.
- Public methods and state transitions.
- Mutable state and thread or process safety.
- Persistence, network, cache, or file-system interactions.
- Failure and degraded behavior.
- Performance expectations.
- Dependencies and forbidden responsibilities.
- Security and privacy boundaries.
- Test strategy.

A class without this contract is incomplete.

### 9.2 Comment quality

Comments explain intent, trade-offs, assumptions, constraints, and non-obvious behavior. They must not restate obvious syntax.

Bare `TODO`, `FIXME`, `HACK`, and `TEMP` comments are prohibited. Temporary markers require an issue identifier, reason, removal condition, and compatibility boundary or deadline where applicable.

## 10. Working method

Before editing:

1. Restate the outcome and user-visible behavior.
2. Inspect the complete path, callers, tests, persistence, contracts, and failure boundaries.
3. Reproduce or otherwise prove the issue.
4. Preserve unrelated worktree changes.
5. Search for existing helpers, patterns, native features, and dependencies.
6. Explain the root cause and choose the smallest correct shared boundary.
7. Split substantial work into independently testable phases.

During implementation:

1. Make one coherent change at a time.
2. Add the smallest meaningful regression test with each non-trivial change.
3. Run focused checks first.
4. Run the complete applicable release gate.
5. Reinspect the diff and original request after tests pass.
6. Continue until every stated requirement is implemented or explicitly documented as blocked.

Do not stop at a plan when implementation was requested unless required user input or unavailable external infrastructure genuinely blocks the work.

## 11. Change-scope rules

- Preserve existing behavior unless the issue explicitly changes it.
- Prefer targeted edits over replacing complete modules, classes, or components.
- Do not perform unrelated refactoring in the same change.
- Do not introduce speculative abstractions.
- Reuse approved existing abstractions where they fit.
- Do not preserve a flawed abstraction merely to avoid a justified correction; document and review substantial corrections first.
- Treat public contracts, database schemas, financial formulas, authentication boundaries, computation identities, model versions, and persisted formats as one-way-door decisions requiring deeper review.
- Preserve public APIs, CLI behavior, output schemas, model versions, and stored data unless the issue explicitly changes them.

## 12. Architecture rules

- Maintain clear separation between domain, application, infrastructure, persistence, API, and presentation responsibilities.
- Financial calculations belong in approved backend domain engines, not routes, UI components, templates, or database triggers.
- Routes and controllers orchestrate requests; they do not contain domain logic.
- Repositories own persistence access. Business services do not embed SQL.
- Provider-specific behavior stays behind provider interfaces and normalization layers.
- The frontend consumes stable contracts and must not independently reinterpret financial formulas.
- Shared behavior has one authoritative implementation.
- Dependency direction points inward toward stable domain contracts.
- Avoid circular dependencies and hidden global state.
- Keep external I/O separate from deterministic calculation.
- Keep Python as the control, provider, API, authorization, billing, explanation, and research plane.
- Use Rust only for approved deterministic CPU-heavy kernels and data-plane operations.

## 13. Documentation and typing

- Public and non-trivial private code must use the project-approved documentation format.
- Every parameter and return value must have an explicit type.
- Python public boundaries must not use implicit `Any`.
- TypeScript `any` is prohibited unless narrowly justified and documented.
- Document nullability, units, currency, time zone, ordering, freshness, error behavior, and side effects.
- Keep documentation synchronized with implementation.
- Use explicit contracts at provider, database, queue, API, model, and native-language boundaries.

## 14. Python and service-code minimum rules

- Keep modules cohesive and dependencies directional.
- Validate once at each trust boundary; do not repeatedly sanitize trusted internal values.
- Use parameterized SQL. Dynamic identifiers require fixed allowlists.
- Keep transactions short and explicit.
- Use bounded, lazy, fork-aware connection pools with health visibility.
- Do not run schema DDL, historical migration, or network initialization on hot read paths.
- Bound every process cache, lock registry, executor queue, retry loop, and external call.
- Expired entries must be evicted rather than merely ignored.
- A timeout does not stop a Python worker thread; concurrency permits remain owned until timed-out work exits.
- Avoid broad exception swallowing. Catch expected errors, preserve useful signals, and fail securely.
- Use structured redacted logs and correlation IDs.
- Prefer bulk database and provider operations over N+1 loops.
- Add query-count tests for backtests, portfolios, and universe operations.

## 15. JavaScript, TypeScript, and client minimum rules

- Use client execution only where it reduces latency or improves interaction without duplicating trusted server logic.
- Prefer native browser APIs and CSS where appropriate.
- Keep event ownership explicit; avoid global listeners and repeated callback registration.
- Never insert untrusted HTML.
- Reserve chart and media dimensions before rendering.
- Draw expensive charts only when visible or requested.
- Handle loading, stale, empty, degraded, error, retry, permission-denied, and offline states intentionally.
- Keep client payloads bounded and versioned.
- Do not move financial models to JavaScript merely to claim client offloading.

## 16. Database minimum rules

- PostgreSQL is the approved relational database unless an accepted architecture decision authorizes another system.
- Access persistence through repositories or approved data-access modules.
- Never use `SELECT *` in application queries.
- Use parameterized queries only.
- Every schema change uses a versioned migration.
- Migrations define rollout, backward compatibility, verification, rollback, or forward recovery.
- Use database constraints to enforce durable invariants.
- Every table documents ownership, writers, readers, retention, update cadence, expected growth, and query patterns.
- Store timestamps in UTC and use timezone-aware values.
- Preserve immutable historical analyses and source lineage.
- Do not overwrite point-in-time financial history.
- Record provider, source timestamp, ingestion timestamp, freshness, and quality status for external data.
- Review indexes against actual query patterns and validate significant queries with execution plans.
- Multi-step writes forming one logical operation are transactional.
- Retried writes and workers are idempotent.
- Prefer `COPY`, staging tables, and set-based operations for bulk ingestion.
- Avoid row-by-row reconstruction in hot scoring paths when compact point-in-time read models can be materialized safely.

## 17. Financial correctness minimum rules

- Document every material formula, input definition, unit, source, rounding policy, currency assumption, date assumption, missing-data rule, and model version.
- Preserve point-in-time correctness.
- Prevent look-ahead bias and survivorship bias.
- Version material methodology changes.
- Never silently convert missing data to zero.
- Distinguish authoritative, calculated, estimated, normalized, stale, degraded, and unavailable values.
- Make provider and filing lineage traceable to final results.
- Add deterministic known-example tests for every material formula.
- Formula changes require explicit review and regression comparison against the prior version.
- Golden fixtures, invariants, boundary cases, and cross-period consistency tests are mandatory for material changes.

Repository-specific financial conventions:

- Graham dividend history must be consecutive; gaps break the qualifying streak.
- Piotroski year-over-year signals use aligned fiscal periods, not arbitrary adjacent records.
- Altman missing components must not silently depress the score; follow the approved partial-data methodology.
- Greenblatt enterprise value has one authoritative implementation; do not duplicate it.
- Portfolio volatility uses the covariance matrix; never assume assets are independent.
- Monte Carlo geometric drift is `mu_geo = mu_arith - sigma^2 / 2` unless a versioned methodology explicitly states otherwise.
- Sortino downside deviation uses all observations `N`, not only the downside count.
- Preserve split, dividend, corporate-action, benchmark, FX, and calendar conventions across every engine.

## 18. Model integration rules

Every new model or engine must:

1. Register a stable contract and version.
2. Declare required inputs, missing-data behavior, outputs, provenance, and interpretation.
3. Join the authoritative analysis pipeline and persisted schema when intended for production.
4. Render in the correct UI section without mixing unrelated domains.
5. Work for newly analyzed securities.
6. Backfill or enqueue idempotent refreshes for already-analyzed securities when required.
7. Avoid recalculating unchanged shared inputs.
8. Add unit, integration, persistence, backfill, contract, and UI-presence tests as applicable.
9. Update the model manifest and methodology documentation.
10. Preserve an explanation layer even when a numeric kernel moves to Rust.

Do not run expensive models with no UI, API, persistence consumer, research purpose, or explicit background purpose.

## 19. Reliability and failure handling

Before implementation identify:

- dependency failures;
- timeouts;
- partial responses;
- stale or malformed data;
- duplicate delivery;
- retries after successful side effects;
- concurrent execution;
- process restart;
- user cancellation;
- unavailable optional sections;
- queue saturation and backpressure;
- native-engine unavailability;
- schema or model-version mismatch.

Use bounded retries with backoff and jitter only when safe. Never retry indefinitely.

Optional section failures must not destroy successful independent results. Return clear degraded-state metadata and allow targeted retry.

Repeatable operations must be idempotent or protected by idempotency keys, uniqueness constraints, locks, leases, or equivalent approved mechanisms.

## 20. Security and privacy minimum rules

- Enforce authorization server-side for every protected resource.
- Isolate all user-owned portfolios, analyses, settings, exports, formulas, jobs, and cached results.
- Validate untrusted input at system boundaries.
- Keep secrets out of code, logs, responses, client bundles, fixtures, and committed files.
- Use centralized secret and configuration management.
- Parameterize database queries.
- Escape or safely render user-controlled output.
- Apply rate limits and abuse controls where appropriate.
- Do not log passwords, tokens, complete payment data, sensitive portfolio contents, or unnecessary personal data.
- Apply least privilege to services, workers, databases, providers, caches, and object storage.
- Security-sensitive changes require explicit threat analysis and tests.
- Shared caches and immutable snapshots must preserve entitlement and tenant boundaries.

## 21. Testing requirements

Testing is based on behavior and risk, not coverage percentage alone.

Applicable tests include:

- Unit tests for business rules.
- Integration tests for database, repository, service, cache, workflow, and native boundaries.
- Contract tests for APIs and providers.
- End-to-end tests for critical user journeys.
- Regression tests for every fixed defect.
- Boundary and invalid-input tests.
- Timeout, retry, partial-failure, cancellation, restart, and degraded-mode tests.
- Migration tests.
- Accessibility tests.
- Deterministic financial-model tests.
- Performance tests for performance-sensitive work.
- Python/Rust parity and fallback tests for native work.
- Property-based tests for invariants where useful.

Tests verify observable behavior rather than implementation details unless the detail is itself a required contract.

Do not delete, weaken, skip, or rewrite failing tests merely to make a change pass.

## 22. Observability requirements

Important operations emit enough structured telemetry to determine:

- what happened;
- whether it succeeded;
- duration and stage timings;
- request, user-safe identifier, job, provider, dataset, model, or worker involved;
- engine choice and fallback use;
- stale or degraded data use;
- failure reason;
- records or users affected;
- CPU, memory, database, cache, payload, queue, and cost impact where material.

Use structured logs, correlation IDs, metrics, traces where useful, and actionable alerts. Never expose secrets or unnecessary personal data.

Every production-critical path defines monitoring and alert ownership before release.

## 23. API and contract rules

- Use explicit request and response schemas.
- Define nullability, units, currency, freshness, pagination, errors, and compatibility expectations.
- Use one stable error-envelope format.
- Evolve contracts backward-compatibly or version them.
- Do not silently rename, remove, or change field meaning.
- Use idempotency protection for repeatable writes.
- Generate and maintain OpenAPI or equivalent documentation.
- Add consumer and provider contract tests.
- Send compact job specifications and version references across service boundaries rather than copying large matrices unnecessarily.

## 24. UI, design, and accessibility rules

- SCSS remains the source of truth where the current application uses SCSS.
- Use approved tokens, maps, functions, mixins, `@use`, and `@forward`.
- Do not scatter hard-coded colors, typography, spacing, radii, shadows, z-indexes, or breakpoints.
- Nest styles according to logical component structure.
- Place responsive mixins inside the selectors they modify.
- Design from 320 px through large desktop and 4K.
- Meet WCAG 2.2 AA.
- Support keyboard navigation, visible focus, semantic structure, screen readers, zoom, reduced motion, and accessible chart/table alternatives.
- Define loading, empty, stale, degraded, permission-denied, and failure states.
- A failed independent section must not crash the complete page.
- Keep Overview and Accounting distinct.
- Use progressive disclosure rather than dashboard clutter.
- Quick Peek must remain useful without scrolling.
- Light and dark modes are equal products.
- Avoid generic card-grid design, excessive rounded corners, default framework styling, and unnecessary motion.

## 25. Performance and resource-efficiency rules

- Measure before optimizing.
- Record baseline, workload, environment, p50, p95, p99, throughput, error rate, CPU, RSS, database queries, bytes read, payload size, and saturation.
- Optimize network and database round trips and repeated work before micro-optimizing syntax.
- Reuse persisted analyses for unchanged authoritative inputs.
- Use immutable computation identities, singleflight, bounded caches, background workflows, and idempotent persistence where they reduce duplicate work.
- Keep web workers free of CPU-heavy and scheduled maintenance work.
- Use bounded concurrency, explicit backpressure, cancellation, and graceful shutdown.
- Prefer bulk operations, compact read models, aligned matrices, memory mapping, and columnar boundaries.
- Localhost benchmarks do not prove production capacity.
- Include serialization, copying, language-boundary, and operational costs in benchmarks.
- The fastest request is one served from an immutable cache or edge without recomputation.

## 26. Dependencies, build-versus-buy, and no-reinvention

Classify every new responsibility as either:

- **Cenvarn-owned meaning:** financial formulas, point-in-time rules, normalization policy, corporate-action interpretation, factor ranking, portfolio-ledger semantics, backtest event behavior, simulation specifications, computation identities, entitlements, narrow adapters, and product-specific explanations.
- **Commodity infrastructure:** use an approved maintained library or platform.

Without an accepted ADR and explicit user approval, do not implement or substantially reimplement:

- HTTP or RPC stacks, connection pools, protocol parsers, TLS, web servers, reverse proxies, or CDN behavior.
- PostgreSQL drivers, database engines, migration engines, object stores, or persistence foundations.
- Workflow engines, queues, schedulers, retry or lease systems, distributed locks, brokers, or durable job stores.
- Redis or Valkey servers, clients, protocols, or generic distributed rate limiting.
- Cryptography, password hashing, JWT/JWS/JWE, OAuth/OIDC, key management, certificate validation, webhook signatures, or random-number generators.
- Payment clients, tax engines, card handling, or Stripe replacements.
- XML, HTML, XBRL, JSON, CSV, Arrow, Parquet, compression, encoding, or serialization foundations. Project-owned normalization may run after maintained parsing.
- DataFrame engines, SQL engines, vector databases, memory allocators, generic concurrency runtimes, matrix decompositions, BLAS/LAPACK, or statistical foundations.
- Date, time-zone, calendar, currency, UUID, decimal, locale, charting, Canvas/WebGL, PDF/spreadsheet rendering, observability SDKs, package managers, build systems, test runners, linters, or formatters.
- A custom C++ application or runtime layer.

Names do not create exceptions. `helper`, `lightweight client`, `simple queue`, `mini framework`, `internal parser`, `temporary adapter`, or `small Rust service` remains prohibited when it owns a commodity responsibility.

An exception requires:

1. A dedicated issue.
2. An accepted ADR.
3. Evaluation of maintained alternatives.
4. Production-shaped benchmarks including operational and boundary cost.
5. Security, privacy, license, maintenance, and supply-chain review.
6. Bounded scope and ownership.
7. Telemetry and support plan.
8. Rollout and rollback plan.
9. Explicit user approval.

The implementing agent may not approve its own exception.

Before adding a dependency document why it is needed, why existing capabilities are insufficient, maintenance and security status, license, runtime and bundle cost, transitive impact, and removal strategy.

Use lockfiles and approved version policies.

## 27. Configuration rules

- Centralize configuration.
- Validate configuration at startup.
- Separate environments explicitly.
- Do not read environment variables throughout arbitrary modules.
- Feature flags require owner, purpose, default, rollout plan, observability, and removal condition.
- Secrets use approved secret management and never appear in logs or client bundles.

## 28. Rust and native-code policy

Rust is an optimization and correctness tool for deterministic CPU-heavy kernels, not a reason to rewrite the product.

Python remains responsible for:

- API and control-plane composition.
- Provider access and rate limiting.
- Authentication, authorization, billing, and entitlements.
- PostgreSQL orchestration.
- Workflow initiation and product-level recovery decisions.
- Explanations, warnings, response formatting, and research iteration.

Rust may own, when benchmarks justify it:

- Price, corporate-action, FX, and point-in-time matrices.
- Returns, rolling statistics, covariance, risk metrics, drawdown, and benchmark alignment.
- Cross-sectional ranking, top-N selection, and rebalance kernels.
- Portfolio valuation and event-driven backtesting.
- Batch factor scoring over compact numeric tables.
- Large Monte Carlo and randomized strategy trials.

Rust must not own commodity infrastructure prohibited above.

### 28.1 Rust migration gate

Before moving code to Rust:

1. Prove the path is CPU- or memory-bound using production-shaped profiling.
2. Remove duplicate loading, row-by-row I/O, unnecessary pandas reconstruction, and avoidable serialization first.
3. Define a language-neutral typed contract.
4. Keep the boundary compact and columnar.
5. Measure conversion and copying cost.
6. Preserve the Python reference implementation until certification.
7. Add deterministic parity fixtures and explicit tolerances.
8. Add automatic Python fallback and engine-choice telemetry.
9. Prove material end-to-end improvement, not only faster isolated arithmetic.
10. Document rollback and dataset/model-version compatibility.

Do not move small dictionary extraction, threshold mapping, explanation generation, provider calls, authorization, billing, or CRUD into Rust.

### 28.2 Model migration rule

Do not rewrite production models one class at a time merely for language consistency.

Keep explanation-rich and threshold-oriented model orchestration in Python. Extract shared batch kernels when they are repeatedly executed across a universe.

Priority native candidates are:

1. Batch price and risk statistics used by momentum, risk metrics, regime, and benchmark models.
2. Cross-sectional ranking used by Greenblatt, factor ranking, screener ranking, top-N selection, and rebalance logic.
3. Batch fundamental trend kernels used across profitability, FCF quality, growth quality, capital allocation, factor momentum, and point-in-time scoring.
4. Event-driven portfolio and backtesting kernels.
5. Large simulation workloads after workload thresholds are proven.

Poor native candidates include small single-company threshold models, provider-bound models, explanation layers, bias labels, market-fear labels, and parsing or orchestration code.

## 29. Deployment and migration safety

For material changes:

- Prefer feature flags and incremental rollout.
- Preserve backward compatibility during transitions.
- Use expand-and-contract database migrations.
- Define health checks and post-deployment verification.
- Define rollback criteria.
- Verify rollback does not corrupt or lose data.
- Retain the prior path until the replacement is proven where practical.
- Document irreversible decisions and forward recovery.
- Keep Python fallback for native engines during certification.

A feature is not production-ready solely because tests pass.

## 30. Pull request requirements

Every pull request must explain:

- What changed.
- Why it changed.
- The verified root cause.
- The written design or issue-resolution document.
- What was intentionally not changed.
- Linked issue and ADRs.
- Standards loaded and applied.
- Existing code or platform features reused.
- Tests and checks actually executed.
- Failure modes considered.
- Security and privacy impact.
- Database and migration impact.
- Financial-methodology impact.
- Performance and resource impact.
- Observability added or changed.
- Deployment and rollback plan.
- Screenshots or recordings for visible UI changes.

Keep pull requests focused and reviewable. Separate unrelated cleanup. Do not self-approve material changes where independent review is available.

## 31. Completion gate

Do not declare a task complete until all applicable items pass:

- Requirements and acceptance criteria are satisfied.
- The issue is solved in writing and the written solution matches the final implementation.
- Applicable standards were loaded and followed.
- Every non-trivial class and function has its required contract and documentation.
- Documentation was written before implementation and reconciled afterward.
- Formatting passes.
- Linting passes.
- Type checking passes.
- Unit, integration, contract, migration, accessibility, performance, parity, fallback, and end-to-end tests pass as applicable.
- Security review is complete as applicable.
- Financial-correctness evidence is complete as applicable.
- Observability and failure handling are implemented.
- No unrelated changes were introduced.
- Generated files and documentation are updated.
- Deployment and rollback implications are documented.
- The final diff was compared against the original issue and written design.

# Safe Change Isolation

Never implement an issue, bug fix, refactor, migration, or experiment directly on `main`.

For every change:

1. Create a dedicated Git branch named for the issue.
2. Use a separate Git worktree when isolation from the current working directory is useful.
3. Write the design, affected systems, failure modes, tests, migration plan, and rollback plan before implementation.
4. Add or update tests that reproduce the defect or prove the intended behavior.
5. Keep the change scoped to the issue. Do not combine unrelated cleanup.
6. Run all relevant unit, integration, contract, migration, security, and end-to-end tests.
7. Open a draft pull request and preserve evidence of the test results.
8. Do not merge while correctness, compatibility, data migration, deployment, or rollback remains uncertain.
9. Use a feature flag, shadow path, or disabled-by-default configuration when incomplete code must be merged safely.
10. Never push directly to `main`.

Create a separate repository only when the work is an independently deployable service, reusable package, isolated research project, or product with a separate ownership and release lifecycle.

Risk alone is not sufficient reason to create another repository. Risky changes should normally be isolated with branches, worktrees, tests, feature flags, and pull-request gates.

The final task report identifies:

1. Files changed.
2. Behavior implemented.
3. Written design or issue-resolution artifact used.
4. Standards applied.
5. Tests and checks actually run.
6. Known limitations or follow-up work.
7. Migration, rollout, and rollback considerations.
8. Performance and resource evidence where relevant.
9. Engine choice and parity evidence for native work.

Never claim a check passed unless it was actually executed and its result was observed.
