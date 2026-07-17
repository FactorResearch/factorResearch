# Purpose

Define the shared engineering requirements that will govern the upcoming Python and JavaScript/TypeScript AI instruction pages.

The objective is to make code consistent, predictable, easy to review, and understandable even when revisited six years later by someone who did not write it.

# Mandatory long-term commenting and documentation standard

Comments and documentation are required wherever they preserve design intent, explain non-obvious behavior, or prevent future developers and AI agents from having to reverse-engineer the code.

Code must remain understandable years after implementation, even when the original author is unavailable.

## Core commenting principle

Comments must explain **why the code exists, why a decision was made, what assumptions it depends on, and what could break if it changes**.

Comments must not merely restate the syntax or describe an obvious line of code.

Good comments preserve context that cannot be recovered easily from the implementation alone.

## Required documentation areas

The Python and JavaScript/TypeScript instruction pages must require documentation for:

- Public modules, packages, classes, functions, methods, hooks, services, repositories, providers, and reusable components.
- Financial formulas, scoring rules, normalization decisions, thresholds, fallback logic, and data-quality assumptions.
- Business rules that are not obvious from the code.
- Workarounds for third-party APIs, browser behavior, framework limitations, provider inconsistencies, or historical data problems.
- Retry, fallback, timeout, caching, rate-limit, stale-data, and degraded-mode behavior.
- Security-sensitive, privacy-sensitive, permission-sensitive, and billing-related logic.
- Performance optimizations whose purpose or tradeoff is not obvious.
- Temporary compatibility code and migration logic.
- Non-obvious regular expressions, date logic, currency handling, time-zone handling, and numerical edge cases.
- Cross-language contracts between Python and JavaScript/TypeScript.
- Any deliberate deviation from the project’s normal architecture or coding standards.

## Python documentation requirements

Python code must use clear, consistent docstrings for public modules, classes, functions, methods, protocols, repositories, providers, and services.

Docstrings must document, where applicable:

- Purpose and responsibility.
- Parameters and their expected meaning.
- Return value and units.
- Raised exceptions.
- Side effects.
- External systems accessed.
- Important assumptions and invariants.
- Financial or business-rule references.

The final Python page must define and enforce one project-wide docstring format. Google-style docstrings are the preferred default unless another format is explicitly selected before implementation.

## JavaScript and TypeScript documentation requirements

JavaScript and TypeScript code must use JSDoc or TSDoc for exported functions, classes, services, hooks, reusable components, public types, and non-obvious utilities.

Documentation must explain behavior not already expressed by the type system. It must not duplicate obvious TypeScript types without adding useful context.

Component and hook documentation should explain:

- User-facing responsibility.
- Data dependencies.
- Loading, empty, stale, degraded, and failure behavior.
- Side effects.
- Accessibility requirements.
- Important performance or memoization decisions.

## Inline-comment placement

Inline comments must be placed immediately above the block they explain.

Avoid end-of-line comments except for short, unambiguous annotations.

Comments must remain synchronized with the code. A misleading or outdated comment is considered a defect and must be updated or removed in the same change that modifies the related behavior.

## Decision and rationale comments

When the implementation contains a decision that a future developer might reasonably replace or question, include a short rationale comment.

Examples include:

- Why a specific fallback order is required.
- Why a calculation uses one data field instead of another.
- Why a cache duration differs from the default.
- Why a section retries independently.
- Why a browser fallback exists.
- Why a seemingly simpler implementation is unsafe or inaccurate.

## TODO and temporary-code rules

Bare `TODO`, `FIXME`, `HACK`, or `TEMP` comments are prohibited.

Every temporary-code marker must include:

- The reason it exists.
- The condition for removal.
- A linked issue or task identifier.
- Any deadline or compatibility boundary when applicable.

Example:

```
TODO(ISSUE_123): Remove the legacy response adapter after all clients use API v2.
```

## Financial-code documentation

Every material financial calculation must document:

- Formula name.
- Input definitions and units.
- Source or methodology reference when applicable.
- Treatment of missing, negative, stale, restated, or anomalous values.
- Rounding policy.
- Currency and date assumptions.
- Whether the output is authoritative, estimated, normalized, or display-only.

Comments must not claim financial certainty when the result is an estimate or model output.

## Comments versus naming

Comments do not excuse unclear code.

The required order is:

1. Use precise names.
2. Keep functions and classes focused.
3. Structure the code logically.
4. Add comments for intent and context that clear code cannot express on its own.

A comment should not be used to compensate for vague names, excessive nesting, duplicated logic, or an oversized function.

## File-level documentation

Complex modules must begin with a short file-level description explaining:

- The module’s responsibility.
- Its architectural layer.
- Its primary dependencies.
- What it must not be responsible for.
- Any important lifecycle, data-flow, or state assumptions.

## Change-history rule

Do not maintain manual change logs inside source files. Git history and linked issues are the source of truth for historical changes.

Comments should describe the current reason and behavior, not narrate every prior revision.

## AI implementation requirement

Before generating or modifying Python or JavaScript/TypeScript code, the AI must:

- Load the applicable language-standard page into active context.
- Inspect nearby code and existing approved documentation patterns.
- Preserve or improve relevant comments and docstrings.
- Update documentation whenever behavior, assumptions, parameters, return values, errors, or side effects change.
- Refuse to mark work complete when public or non-obvious behavior remains undocumented.

## Review and enforcement

Code review and CI must reject:

- Missing required public documentation.
- Bare TODO or FIXME comments.
- Comments that merely restate obvious code.
- Outdated comments contradicted by implementation.
- Unexplained financial formulas or thresholds.
- Temporary workarounds without an issue reference and removal condition.
- Exported APIs whose behavior, errors, side effects, or assumptions are unclear.

## Acceptance criteria

- A developer unfamiliar with the feature can understand its purpose and constraints without contacting the original author.
- Important business and financial decisions are preserved in the codebase.
- Public APIs and architectural boundaries are documented consistently.
- Comments remain concise, accurate, useful, and synchronized with behavior.
- Code can be revisited years later without requiring extensive reverse engineering.

# Planned instruction pages

The final standards will be split into two dedicated AI instruction pages:

1. Python Engineering Standards
2. JavaScript and TypeScript Engineering Standards

Both pages must inherit this commenting and long-term documentation standard.

# Mandatory class and function documentation templates

Every class, function, method, hook, service, repository, provider, validator, and reusable component must follow a predictable documentation template. Documentation is required before the implementation body and must remain synchronized with the code.

## Class documentation requirements

Every class must have a broad explanation placed immediately above or inside the class declaration using the language-standard documentation format.

The class documentation must explain:

- The class's primary responsibility.
- Why the class exists and which architectural layer it belongs to.
- What business or technical problem it solves.
- What the class owns and what it must not own.
- Its important dependencies and collaborators.
- Its lifecycle and expected usage.
- Important state, invariants, assumptions, side effects, and thread or concurrency considerations.
- External systems, databases, caches, APIs, browser APIs, or services it accesses.
- Relevant failure, retry, fallback, timeout, and degraded-mode behavior.
- One concise usage example when the intended usage is not obvious.

Broad class documentation must provide enough context for a developer who has never seen the project to understand where the class fits without reading the entire file.

## Function and method documentation requirements

Every function and method must have a documentation block immediately before its declaration. This applies to public and private functions. Very small language-required accessors may be exempt only when their behavior is fully obvious and the applicable language-standard page explicitly permits the exemption.

Each function documentation block must explain:

- What the function does.
- Why it exists when the reason is not obvious.
- The operation's important steps or decision flow.
- Every accepted parameter.
- The semantic meaning of each parameter, not only its programming type.
- Parameter units, format, allowed range, optionality, defaults, and validation rules where applicable.
- The function's explicit return type.
- What the returned value represents.
- Return units, shape, ordering, nullability, and important guarantees.
- Exceptions or errors it may raise, throw, return, or translate.
- Side effects such as database writes, network requests, cache updates, logging, analytics, file access, or state mutation.
- Important assumptions, invariants, edge cases, fallback behavior, and performance implications.

A reader must not need to inspect the function body to determine what inputs are accepted or what output is returned.

## Mandatory type declarations

Python functions and methods must declare parameter types and return types using Python type annotations.

JavaScript production code should be TypeScript. TypeScript functions and methods must declare parameter types and explicit return types. Plain JavaScript exceptions must use complete JSDoc type declarations.

The following are prohibited unless narrowly justified and documented:

- Missing return types on exported or reusable functions.
- Implicit `Any` in Python public boundaries.
- TypeScript `any`.
- Ambiguous dictionary or object return values without a named schema, type, interface, dataclass, or model.
- Returning different unrelated types from the same function.
- Undocumented `null`, `None`, or `undefined` behavior.

## Required Python documentation template

Python must use the project-approved docstring convention consistently. Google-style docstrings are the default.

```python
class PortfolioAnalysisService:
    """Coordinate portfolio analysis across scoring and market-data services.

    This application-layer service validates a portfolio, retrieves the
    normalized inputs required by the analysis engines, coordinates each
    independent calculation, and assembles the final analysis response.

    The class does not implement financial formulas or access the database
    directly. Those responsibilities belong to domain engines and repository
    abstractions respectively.

    Attributes:
        portfolio_repository: Retrieves and persists portfolio information.
        market_data_provider: Supplies normalized market and fundamental data.
        logger: Records operational context without exposing user-sensitive data.
    """

    def analyze_portfolio(
        self,
        portfolio_id: PortfolioId,
        as_of_date: date,
    ) -> PortfolioAnalysis:
        """Run a complete analysis for one portfolio at a specific date.

        Validates that the portfolio exists and contains supported holdings,
        retrieves point-in-time market data, executes each independent analysis
        section, and returns a normalized aggregate result. A failure in one
        optional section is captured as a section-level failure and does not
        discard successful sections.

        Args:
            portfolio_id: Stable identifier of the portfolio to analyze.
            as_of_date: Point-in-time date used for market and fundamental data.
                Future dates are rejected.

        Returns:
            A PortfolioAnalysis containing successful section results, data
            freshness metadata, warnings, and any recoverable section failures.

        Raises:
            PortfolioNotFoundError: If no portfolio exists for portfolio_id.
            InvalidAnalysisDateError: If as_of_date is unsupported or in the future.
            MarketDataUnavailableError: If required baseline data cannot be loaded.

        Side Effects:
            Reads portfolio and market data, writes structured logs, and may
            populate approved caches. It does not modify portfolio holdings.
        """
```

## Required TypeScript documentation template

TypeScript must use TSDoc or JSDoc consistently for classes, functions, methods, hooks, components, and exported APIs.

```tsx
/**
 * Coordinates portfolio analysis requests and normalizes section-level results.
 *
 * This application service validates the request, invokes independent analysis
 * providers, preserves successful sections when an optional section fails, and
 * returns one stable contract to the UI.
 *
 * It does not contain financial formulas and does not access persistence
 * directly. Those concerns belong to domain engines and repositories.
 */
export class PortfolioAnalysisService {
    /**
     * Runs portfolio analysis for a specific point-in-time date.
     *
     * @param portfolioId - Stable identifier of the portfolio to analyze.
     * @param asOfDate - Point-in-time date used to select market and fundamental
     * data. Future dates are rejected.
     * @returns A normalized analysis containing successful section results,
     * freshness metadata, warnings, and recoverable section failures.
     * @throws PortfolioNotFoundError When the portfolio does not exist.
     * @throws InvalidAnalysisDateError When the requested date is unsupported.
     * @throws MarketDataUnavailableError When required baseline data is unavailable.
     *
     * @remarks
     * This method may read through repositories, populate approved caches, and
     * emit structured logs. It never mutates the portfolio's holdings.
     */
    public async analyzePortfolio(
        portfolioId: PortfolioId,
        asOfDate: Date,
    ): Promise<PortfolioAnalysis> {
        // Implementation
    }
}
```

## Naming and documentation alignment

Function and method names must describe the action and business object clearly. Documentation must agree with the name and declared types.

Prohibited vague names include:

- `processData`
- `handleStuff`
- `doWork`
- `runTask`
- `manageItems`
- `getResult`
- `helper`

Names must be specific enough that the function's primary purpose is visible at the call site, while the documentation supplies full behavior, constraints, and context.

## Documentation placement and formatting

- Documentation must appear immediately before the declaration it documents.
- Do not place a large group of function descriptions at the top of the file separated from their implementations.
- Decorators and annotations may appear between documentation and declaration only where required by the language's standard syntax.
- Keep parameter documentation in the same order as the function signature.
- Keep return and error documentation current when implementation behavior changes.
- Comments must use complete, clear sentences and professional language.
- Avoid unexplained acronyms. Define domain-specific terminology on first use.

## Enforcement and acceptance criteria

Code review and CI must reject:

- Classes without a broad responsibility explanation.
- Functions or methods without the required documentation block.
- Missing parameter or return types.
- Parameters present in the signature but absent from documentation.
- Documented parameters that no longer exist.
- Missing or ambiguous return-value documentation.
- Undocumented exceptions, side effects, nullability, units, or important edge cases.
- Documentation that simply repeats the function name without explaining behavior.
- Documentation contradicted by the implementation.

A class or function is not complete until its declaration, types, documentation, implementation, and tests describe the same contract.

# Mandatory comment-first implementation workflow

Before writing or modifying implementation code, the AI agent must first write the explanatory comments, docstrings, or TSDoc/JSDoc that define the intended behavior.

This is a blocking workflow requirement intended to make the agent reason through the design before implementation, reduce accidental overwrites, and prevent unnecessary abstraction or over-engineering.

## Required order of work

For every new class, function, method, hook, service, repository, provider, component, or non-trivial code block, the agent must follow this order:

1. Write the class-level or function-level documentation first.
2. Define the responsibility, inputs, outputs, side effects, errors, assumptions, and edge cases.
3. Confirm the scope is narrow and does not duplicate an existing abstraction.
4. Implement only the behavior described by the documentation.
5. Re-read the completed implementation and update the documentation if the behavior differs.
6. Run formatting, linting, type checking, and tests before marking the task complete.

The agent must not write a large implementation first and add comments afterward as a documentation pass.

## Comment-first planning requirements

Before implementation begins, the documentation must make clear:

- Why the class or function is needed.
- What exact responsibility it owns.
- What it must not be responsible for.
- Which parameters it accepts and why each exists.
- What type, format, unit, range, and validation rules apply to each parameter.
- What is returned, including type, meaning, units, and empty or failure behavior.
- Which exceptions or error states are possible.
- Which side effects occur.
- Which external systems, repositories, providers, caches, or APIs are touched.
- Which assumptions, invariants, fallbacks, and edge cases apply.
- Whether an existing function, class, or shared utility should be reused instead.

## Anti-overwriting rule

Before modifying an existing class or function, the agent must read its current documentation and nearby implementation first.

The agent must preserve existing behavior unless the task explicitly requires changing it. It must not replace a complete class, module, or function when a targeted edit is sufficient.

The preferred order is:

1. Understand the existing contract.
2. Document the intended change.
3. Make the smallest safe implementation change.
4. Update only the affected tests and documentation.

## Anti-over-engineering rule

The comment-first step must be used to challenge unnecessary complexity before code is written.

The agent must not introduce:

- A new class when a focused function is sufficient.
- A new abstraction for a single one-off use without a clear future control point.
- A new service, repository, manager, helper, factory, adapter, or wrapper that duplicates an existing responsibility.
- Generic frameworks for hypothetical requirements not present in the task.
- Configuration options that have no current consumer.
- Premature extensibility that makes the current behavior harder to understand.

If the planned documentation cannot describe a narrow and concrete responsibility, the code must be simplified before implementation.

## Required implementation-note evidence

For each completed task, the agent's implementation notes must state:

- That documentation was written before implementation.
- Which existing code and contracts were inspected.
- Why the chosen implementation is the smallest suitable change.
- Which existing abstractions were reused.
- Which tests, linting, formatting, and type checks passed.

## Review and enforcement

Code review must reject:

- Implementations created before required documentation.
- Comments that were clearly added afterward and do not match the design process.
- Broad rewrites where a targeted modification was possible.
- New abstractions without a documented current need.
- Code whose implementation exceeds the responsibility described by its comments.
- Documentation that describes behavior not implemented by the code.

A task is not complete until the comment-first workflow and its implementation evidence are present.

# Engineering lifecycle, ownership, and operational standards

These standards extend the code-writing rules into the full engineering lifecycle. A feature is not complete merely because the implementation compiles or tests pass. It must be understandable, reviewable, observable, reversible, secure, supportable, and safe to operate in production.

## Work-backwards requirement

Before implementing a meaningful feature or system, the agent must document:

- The user or internal customer.
- The problem being solved.
- The expected user experience.
- The measurable success criteria.
- The explicit non-goals.
- The smallest viable solution.
- Why existing functionality is insufficient.
- The main risks and trade-offs.

Small changes may use a concise implementation brief. Large or high-risk changes require a full design document.

## One-way-door and two-way-door decisions

Every material architectural decision must be classified before implementation:

- **Two-way door:** inexpensive, low-risk, and easy to reverse. These decisions should move quickly with lightweight review.
- **One-way door:** difficult, expensive, data-destructive, contract-breaking, or operationally risky to reverse. These decisions require deeper review, migration planning, rollback planning, and explicit approval.

Examples of one-way-door decisions include permanent schema changes, public API contract changes, destructive migrations, security-model changes, and financial-calculation changes that alter historical results.

The agent must not apply enterprise-level ceremony to every reversible change. The purpose of this classification is to increase rigor where necessary while preventing over-engineering elsewhere.

## Mandatory design document for substantial changes

A substantial feature, service, migration, data model, external provider integration, or architectural change must have a design document before implementation.

The design document must include:

- Problem statement.
- Current system and current limitations.
- Proposed design.
- Responsibilities and boundaries.
- Data flow and state transitions.
- Public interfaces and contracts.
- Alternatives considered.
- Trade-offs and rejected options.
- Failure modes.
- Security and privacy implications.
- Performance and scalability implications.
- Cost implications.
- Migration strategy.
- Rollback strategy.
- Test strategy.
- Observability requirements.
- Deployment strategy.
- Open questions and unresolved risks.

The document must state what the design deliberately does not solve.

## Explicit ownership

Every production feature, service, scheduled job, provider integration, database, and critical workflow must identify:

- Primary owner.
- Backup owner or owning team.
- Upstream and downstream dependencies.
- Operational responsibilities.
- Relevant dashboards and alerts.
- Runbook location.
- Known risks.
- Last review date.

Code without a clear long-term owner must not be treated as production-ready.

## Operational readiness review

Before production release, every meaningful feature must pass an operational readiness review.

Required review areas:

- Structured logging.
- Metrics.
- Tracing or correlation identifiers where applicable.
- Dashboards.
- Alerts with an identified owner.
- Timeouts.
- Retry limits.
- Exponential backoff and jitter where retries are appropriate.
- Rate-limit behavior.
- Cache behavior and stale-data handling.
- Partial-failure behavior.
- Degraded-mode behavior.
- Feature flags where appropriate.
- Rollback procedure.
- Data migration validation.
- Security review.
- Privacy review.
- Load or stress testing where relevant.
- Cost-impact review.
- Support and incident runbook.

A feature must not launch with the assumption that failures will be debugged manually after release.

## Failure-mode analysis

Before implementing a critical workflow or external integration, the agent must reason through and document:

- What can fail.
- How each failure is detected.
- What the user sees.
- What is logged.
- Whether partial success is possible.
- Whether the operation can be safely retried.
- Whether the operation is idempotent.
- Whether duplicate requests are possible.
- Whether a timeout can occur after the remote system has already succeeded.
- Whether retries can amplify a failure.
- Whether stale or incomplete data can be returned.
- Whether fallback data changes the meaning or quality of the result.
- How recovery occurs.

Retries must be bounded. Infinite retries and unbounded retry loops are prohibited.

## Correction-of-error process

Every meaningful production incident, data-integrity failure, security event, or repeated operational defect must result in a written correction-of-error review.

The review must include:

- Customer impact.
- Start and end time.
- Exact timeline.
- Detection method.
- Immediate response.
- Root cause.
- Contributing conditions.
- Why existing safeguards failed.
- Why tests or monitoring did not catch the problem earlier.
- What went well.
- What went poorly.
- Corrective actions.
- Owners and deadlines.
- How recurrence will be prevented.
- Whether similar systems share the same weakness.

Blame-based conclusions such as “the developer made a mistake” are prohibited as root causes. The review must identify why the system allowed one mistake to create customer impact.

## Pull-request and code-review template

Every material pull request must document:

- What changed.
- Why the change is required.
- What was intentionally not changed.
- Linked issue and design document.
- Decision classification: one-way door or two-way door.
- Test evidence.
- Edge cases tested.
- Failure paths tested.
- Public-contract impact.
- Database or migration impact.
- Financial-calculation impact.
- Security and privacy impact.
- Monitoring and logging added or changed.
- Rollback method.
- Screenshots for user-interface work.
- Documentation updates.

Review rules:

- Material changes require independent review.
- Smaller focused pull requests are preferred.
- Unrelated cleanup must be placed in a separate change.
- Reviewers must understand the behavior and risk, not merely confirm that automated checks passed.
- Large rewrites require explicit justification.

## Risk-based testing strategy

Testing requirements must be based on customer and system risk, not only a coverage percentage.

Required test categories where applicable:

- Unit tests for business and domain rules.
- Contract tests for external providers and cross-language boundaries.
- Integration tests for database, cache, queue, and API workflows.
- End-to-end tests for critical user journeys.
- Regression tests for every fixed production defect.
- Boundary-value tests.
- Invalid-input tests.
- Failure-path tests.
- Timeout, retry, and fallback tests.
- Data-quality tests.
- Authorization and isolation tests.
- Accessibility tests.
- Performance and load tests.
- Property-based tests for important financial formulas when useful.

Coverage metrics may reveal missing tests, but coverage alone must never be accepted as evidence of correctness.

## API and data-contract discipline

Every internal and external boundary must define an explicit versioned contract.

Contracts must document:

- Request type.
- Response type.
- Required and optional fields.
- Nullability.
- Units.
- Currency.
- Time zone and date semantics.
- Ordering guarantees.
- Error codes and error shape.
- Pagination.
- Idempotency behavior.
- Freshness metadata.
- Backward-compatibility policy.
- Deprecation policy.
- Whether each value is authoritative, estimated, normalized, cached, stale, or display-only.

The frontend must not independently recreate authoritative backend financial calculations. Shared contracts must prevent Python and TypeScript from assigning different meanings to the same field.

## Dependency-management standard

Before adding a third-party dependency, the change must document:

- Why the dependency is necessary.
- Why existing project capabilities are insufficient.
- Maintenance activity.
- License compatibility.
- Security history.
- Runtime, bundle, memory, and startup impact.
- Transitive dependency impact.
- Upgrade strategy.
- Exit or replacement strategy.
- Whether the dependency controls a critical architectural boundary.

Required controls:

- Lock dependency versions.
- Run automated vulnerability scans.
- Review dependency updates regularly.
- Avoid abandoned packages for critical functionality.
- Do not add a dependency for trivial behavior that can be safely and clearly implemented internally.

## Security and privacy by default

Every feature must evaluate:

- Authentication requirements.
- Authorization rules.
- User and tenant isolation.
- Input validation.
- Output encoding.
- Secret management.
- Sensitive-data exposure in logs.
- Rate limiting.
- Query parameterization.
- Audit logging.
- Data retention.
- Data deletion.
- Encryption requirements.
- Abuse and enumeration risks.

Security and privacy are design inputs, not final cleanup tasks.

## Observability standard

Every important operation must make it possible to determine:

- Whether it ran.
- Whether it succeeded.
- How long it took.
- Why it failed.
- Which provider, fallback, or data source was used.
- Whether the result was fresh, stale, partial, or degraded.
- Which request, user-safe identifier, or background job triggered it.
- How many customers or records were affected.

Required practices:

- Structured logs.
- Stable event and metric names.
- Correlation identifiers.
- No secrets or unnecessary personal data in logs.
- Actionable alerts.
- Alert ownership.
- Alert deduplication.
- Dashboards based on customer impact as well as infrastructure health.

Logging must provide diagnostic context without becoming a substitute for proper error handling.

## Deployment and migration safety

Meaningful production changes must use the safest practical release method.

Required practices where applicable:

- Feature flags.
- Incremental rollout.
- Canary or internal-user release.
- Health checks.
- Post-deployment verification.
- Automated rollback criteria.
- Backward-compatible API and database changes.
- Expand-and-contract database migrations.
- Separate destructive schema removal from the release that stops using the old schema.
- Tested rollback procedure.
- Retention of the old path until the new path is proven stable.

A migration is not complete until data integrity and rollback assumptions have been verified.

## Mechanisms over reminders

Engineering requirements must be enforced through repeatable mechanisms whenever possible.

Preferred mechanisms include:

- Required pull-request templates.
- CI gates.
- Linters.
- Formatters.
- Type checkers.
- Architecture tests.
- Contract tests.
- Required reviewers or code owners.
- Security and dependency scanners.
- Release checklists.
- Automated migration checks.
- Scheduled documentation and ownership reviews.

A rule that depends only on a developer or AI agent remembering it is incomplete.

## AI pre-implementation lifecycle

Before implementing a non-trivial change, the AI agent must follow this sequence:

1. Load the applicable engineering and language standards.
2. Read the relevant existing code and documentation.
3. Identify the customer problem and intended outcome.
4. Classify the decision as a one-way door or two-way door.
5. Search for an existing reusable implementation.
6. Write or update the design and contract documentation.
7. Write class and function documentation before implementation.
8. Implement the smallest safe change.
9. Add or update tests based on risk.
10. Add observability and failure handling.
11. Run formatting, linting, type checking, tests, and security checks.
12. Verify documentation matches the final behavior.
13. Document deployment, migration, and rollback implications.

The agent must not mark work complete when implementation exists without the required operational, testing, ownership, and documentation mechanisms.

## Final engineering acceptance criteria

A production change is complete only when:

- The customer problem and success criteria are clear.
- Scope and non-goals are explicit.
- Architectural decisions are documented.
- Ownership is assigned.
- Public contracts are typed and documented.
- Code follows the language-specific standards.
- Comments and documentation precede and match implementation.
- Tests cover critical behavior and failure paths.
- Security and privacy implications are addressed.
- Logs, metrics, and alerts support production diagnosis.
- Deployment and rollback are safe.
- Migrations are backward-compatible and verified.
- Known risks are documented.
- Review evidence exists.
- A developer unfamiliar with the code can maintain and operate it years later.

# Planned standards document set

The engineering standards should ultimately be organized into three mandatory AI instruction pages:

1. **Python Engineering Standards** — Python structure, naming, typing, documentation, testing, error handling, and tooling.
2. **JavaScript and TypeScript Engineering Standards** — frontend and Node structure, naming, strict typing, components, state, contracts, testing, and tooling.
3. **Engineering Development and Operational Standards** — work-backwards planning, decision classification, design review, ownership, operational readiness, deployment, incident learning, and enforcement mechanisms.

All three pages must be loaded before an AI agent begins substantial cross-stack or production-facing work.