# Factor Research — AI Engineering Instructions

## 1. Authority and scope

This file is the mandatory entry point for every AI coding task in this repository.

These instructions apply to all files under this directory unless a more specific nested `AGENTS.md` exists. A nested file may add stricter local rules but must not weaken repository-wide safety, security, testing, documentation, financial-correctness, or data-integrity requirements.

Notion contains the full engineering standards. This file defines which standards must be loaded and the minimum rules that always apply.

Do not rely on memory from previous conversations or coding sessions. Reload the current repository instructions and applicable standards for every new task.

## 1.1 Repository documentation layout

The repository uses the following documentation structure.

Repository standards:
- docs/engineering.md
- docs/frontend.md
- docs/api.md
- docs/database.md
- docs/testing.md
- docs/security.md
- docs/log.md
- docs/workers.md
- docs/caching.md
- docs/financial.md
- docs/data-providers.md
- docs/config.md
- docs/dependency.md
- docs/release.md
- docs/accessibility.md
- docs/git.md
- docs/ui.md

Always load documents using these repository paths.
Do not assume names from memory.

## 2. Mandatory startup sequence

Before writing or modifying code:

1. Read this entire file.
2. Read the issue, specification, design reference, and acceptance criteria.
3. Inspect the affected files and nearby implementations before proposing changes.
4. Identify every architectural layer affected by the task.
5. Load the mandatory core standards.
6. Load each applicable specialist standard from the routing matrix below.
7. Search for existing functions, services, components, schemas, utilities, and abstractions that may already solve the problem.
8. Define the intended behavior, boundaries, failure modes, tests, and rollback implications before implementation.
9. Make the smallest complete change that satisfies the requirement.
10. Run all required validation before declaring completion.

Do not begin implementation while the required standards or relevant repository context are missing.

## 3. Mandatory core standards

Load and apply these standards for every coding task:

- Engineering Code Standards
- Applicable Python Engineering Standards
- Applicable JavaScript and TypeScript Engineering Standards
- Testing Engineering Standards
- Security Engineering Standards
- Git and Pull Request Standards
- AI Standards Loading and Task Routing Policy

A task that touches both Python and TypeScript must load both language standards.

## 4. Specialist standards routing matrix

Load every standard corresponding to an affected area:

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
| New or upgraded package | Dependency and Package Standards; Security Engineering Standards |
| Performance-sensitive path | Performance Engineering Standards; Observability and Logging Standards |
| Deployment, schema rollout, production migration, incident remediation | Release and Incident Standards; Observability and Logging Standards |
| Cross-cutting feature | Load all standards for every affected layer |

Do not load every full standard for an unrelated one-line change. Load the core set plus all standards relevant to the actual impact of the task.

## 5. Comment-first implementation workflow

For every new or modified non-trivial class, function, method, hook, component, service, repository, provider, worker, query, or financial calculation:

1. Write or update its documentation first.
2. Define responsibility, inputs, outputs, side effects, errors, assumptions, invariants, edge cases, degraded behavior, and external dependencies.
3. Confirm the responsibility does not duplicate an existing abstraction.
4. Implement only the documented behavior.
5. Reconcile documentation, types, implementation, and tests before completion.

Do not write a large implementation first and add comments afterward.

Comments must explain intent, trade-offs, assumptions, and non-obvious behavior. They must not restate obvious syntax.

## 6. Change-scope rules

- Read existing documentation and nearby code before modification.
- Preserve existing behavior unless the task explicitly changes it.
- Prefer targeted edits over replacing complete modules, classes, or components.
- Do not perform unrelated refactoring in the same change.
- Do not introduce speculative abstractions for hypothetical future needs.
- Reuse approved existing abstractions where they fit.
- Do not preserve a flawed abstraction merely to avoid a justified design correction; document and review substantial corrections before implementation.
- Treat public contracts, database schemas, financial formulas, authentication boundaries, and persisted data formats as one-way-door decisions requiring deeper review.

## 7. Architecture rules

- Maintain clear separation between domain, application, infrastructure, persistence, API, and presentation responsibilities.
- Financial calculations belong in approved backend domain engines, not routes, UI components, templates, or database triggers.
- Routes and controllers orchestrate requests; they do not contain domain logic.
- Repositories own persistence access. Business services do not embed SQL.
- Provider-specific behavior stays behind provider interfaces and normalization layers.
- The frontend consumes stable contracts and must not independently reinterpret financial formulas.
- Shared behavior must have one authoritative implementation.
- Dependency direction must point inward toward stable domain contracts.
- Avoid circular dependencies and hidden global state.

## 8. Documentation and typing

- Public and non-trivial private code must use the project-approved documentation format.
- Every parameter and return value must have an explicit type.
- Python public boundaries must not use implicit `Any`.
- TypeScript `any` is prohibited unless narrowly justified and documented.
- Document nullability, units, currency, time zone, ordering, freshness, error behavior, and side effects where applicable.
- Keep comments and documentation synchronized with implementation.
- Bare `TODO`, `FIXME`, `HACK`, and `TEMP` comments are prohibited.
- Temporary markers require an issue identifier, reason, removal condition, and compatibility boundary or deadline where applicable.

## 9. Database minimum rules

- Use PostgreSQL as the approved relational database unless an architecture decision explicitly authorizes another system.
- Access persistence through repositories or approved data-access modules.
- Never use `SELECT *` in application queries.
- Use parameterized queries only.
- Every schema change must use a versioned migration.
- Migrations must define rollout, backward compatibility, verification, and rollback or forward-recovery strategy.
- Use database constraints to enforce durable invariants.
- Every table must have documented ownership, writers, readers, retention, update cadence, expected growth, and query patterns.
- Store timestamps in UTC and use timezone-aware values.
- Preserve immutable historical financial analyses and source lineage.
- Do not overwrite point-in-time financial history.
- Record provider, source timestamp, ingestion timestamp, freshness, and quality status for externally sourced financial data where applicable.
- Review indexes against actual query patterns and validate significant queries with execution plans.
- Multi-step writes that form one logical operation must be transactional.
- Design write operations and workers to be idempotent where retries are possible.

## 10. Financial correctness minimum rules

- Document every material formula, input definition, unit, source, rounding policy, currency assumption, date assumption, and missing-data rule.
- Preserve point-in-time correctness.
- Prevent look-ahead bias and survivorship bias in historical analysis and backtesting.
- Version material model and methodology changes.
- Do not silently substitute missing values with zero.
- Distinguish authoritative, calculated, estimated, normalized, stale, and unavailable values.
- Make provider and filing lineage traceable to the final result.
- Add deterministic tests using known examples for every material formula.
- Changes to financial formulas require explicit review and regression comparison against the prior version.

## 11. Reliability and failure handling

Before implementation, identify:

- dependency failures
- timeouts
- partial responses
- stale or malformed data
- duplicate delivery
- retries after successful side effects
- concurrent execution
- process restart
- user cancellation
- unavailable optional sections

Use bounded retries with backoff and jitter where retries are safe. Never retry indefinitely.

Optional section failures must not destroy successful independent results. Return clear degraded-state metadata and allow targeted retry where appropriate.

Operations that can be repeated must be idempotent or protected by idempotency keys, uniqueness constraints, locks, or equivalent mechanisms.

## 12. Security and privacy minimum rules

- Enforce authorization server-side for every protected resource.
- Isolate all user-owned portfolios, analyses, settings, exports, and saved formulas.
- Validate untrusted input at system boundaries.
- Keep secrets out of code, logs, responses, client bundles, fixtures, and committed files.
- Use centralized secret and configuration management.
- Parameterize database queries.
- Escape or safely render user-controlled output.
- Apply rate limits and abuse controls to exposed endpoints where appropriate.
- Do not log passwords, tokens, complete payment data, sensitive portfolio contents, or unnecessary personal data.
- Apply least privilege to services, workers, databases, and providers.
- Security-sensitive changes require explicit threat analysis and tests.

## 13. Testing requirements

Testing must be based on risk and behavior, not coverage percentage alone.

Every change must include the applicable tests:

- unit tests for business rules
- integration tests for database, repository, and service boundaries
- contract tests for APIs and providers
- end-to-end tests for critical user journeys
- regression tests for every fixed production defect
- boundary and invalid-input tests
- timeout, retry, partial-failure, and degraded-mode tests
- migration tests for schema changes
- accessibility tests for UI work
- deterministic financial-model tests for calculation changes
- performance tests for performance-sensitive work

Tests must verify observable behavior rather than internal implementation details unless the implementation detail is itself a required contract.

Do not delete, weaken, or skip failing tests merely to make a change pass.

## 14. Observability requirements

Important operations must emit enough structured telemetry to determine:

- what happened
- whether it succeeded
- how long it took
- which request, user-safe identifier, job, provider, or worker was involved
- whether fallback or stale data was used
- why it failed
- how many users or records were affected

Use structured logs, correlation IDs, meaningful metrics, traces where useful, and actionable alerts.

Do not expose secrets or unnecessary personal data in telemetry.

Every new production-critical path must define monitoring and alert ownership before release.

## 15. API and contract rules

- Use explicit request and response schemas.
- Define nullability, units, currency, freshness, pagination, errors, and compatibility expectations.
- Use one stable error-envelope format.
- Version or evolve contracts backward-compatibly.
- Do not silently rename, remove, or change the meaning of existing fields.
- Use idempotency protection for repeatable write requests where duplicate submission is possible.
- Generate and maintain OpenAPI or equivalent contract documentation where applicable.
- Add contract tests for consumers and providers.

## 16. UI and accessibility rules

- Use the approved SCSS architecture, tokens, maps, functions, and mixins.
- Do not hardcode colors, typography, spacing, radii, shadows, z-index, or breakpoints in component styles.
- Use `@use` and `@forward`, not legacy `@import`.
- Nest SCSS according to logical DOM hierarchy.
- Place responsive mixins inside the selector they modify.
- Design from 320 px through large desktop and 4K layouts.
- Meet WCAG 2.2 AA requirements.
- Support keyboard navigation, visible focus, semantic structure, screen readers, zoom, reduced motion, and accessible chart/table alternatives.
- Define loading, empty, stale, degraded, permission-denied, and failure states.
- A failed independent section must not crash the complete page.

## 17. Dependencies and configuration

Before adding a dependency, document:

- why it is needed
- why existing code or platform capability is insufficient
- maintenance and security status
- license compatibility
- runtime, bundle, and transitive-dependency impact
- replacement or removal strategy

Use lockfiles and approved version policies.

Configuration must be centralized, typed or validated at startup, documented, and separated by environment. Do not read environment variables throughout arbitrary modules.

Feature flags must have an owner, purpose, default, rollout plan, observability, and removal condition.

## 18. Deployment and migration safety

For material changes:

- prefer feature flags and incremental rollout
- preserve backward compatibility during transitions
- use expand-and-contract database migrations
- define health checks and post-deployment verification
- define automated or manual rollback criteria
- verify that rollback does not corrupt or lose data
- retain the prior path until the new path is proven where practical
- document irreversible decisions and forward-recovery procedures

A feature is not production-ready solely because tests pass.

## 19. Pull request requirements

Every pull request must explain:

- what changed
- why it changed
- what was intentionally not changed
- linked issue or design document
- standards loaded and applied
- tests performed
- failure modes considered
- security and privacy impact
- database and migration impact
- financial-methodology impact
- performance impact
- observability added or changed
- deployment and rollback plan
- screenshots or recordings for visible UI changes

Keep pull requests focused and reviewable. Separate unrelated cleanup.

Do not self-approve material changes where independent review is available.

## 20. Completion gate

Do not declare the task complete until all applicable items pass:

- requirements and acceptance criteria satisfied
- applicable standards loaded and followed
- documentation written before and reconciled after implementation
- formatting passes
- linting passes
- type checking passes
- unit, integration, contract, and end-to-end tests pass as applicable
- migrations validated as applicable
- security review completed as applicable
- accessibility verified as applicable
- performance verified as applicable
- observability and failure handling implemented
- no unrelated changes introduced
- generated files and documentation updated
- deployment and rollback implications documented

The final task report must identify:

1. Files changed.
2. Behavior implemented.
3. Standards applied.
4. Tests and checks run.
5. Known limitations or follow-up work.
6. Migration, rollout, and rollback considerations.

Never claim a check passed unless it was actually executed and its result was observed.