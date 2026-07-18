# Purpose
Define a risk-based testing strategy that proves business correctness, protects financial calculations, and prevents regressions.
# Core principles
- Tests verify behavior and contracts, not implementation trivia.
- Coverage percentage is a diagnostic, not proof of correctness.
- Every production defect must receive a regression test.
- Failure paths are first-class test cases.
# Required test layers
- Unit tests for isolated domain and business rules.
- Integration tests for databases, repositories, caches, queues, and provider adapters.
- Contract tests for API and provider boundaries.
- End-to-end tests for critical user journeys.
- Migration tests for schema changes and rollback paths.
- Performance and load tests for critical paths.
- Security tests for authorization, tenant isolation, and input handling.
# Financial testing
Every material formula must include:
- Known-answer examples.
- Boundary, missing-value, negative-value, stale-data, restatement, currency, split, and rounding tests.
- Point-in-time correctness tests.
- Look-ahead and survivorship-bias protections where applicable.
- Versioned expected outputs when model definitions change.
# Test design
- Use descriptive names expressing scenario and expected result.
- Prefer deterministic fixtures.
- Freeze time explicitly when dates matter.
- Avoid shared mutable state.
- Mock only true boundaries; do not mock the behavior under test.
- Do not overuse snapshots for business logic.
# CI enforcement
CI must run formatting, linting, type checks, unit tests, integration tests, contract checks, migration tests, and selected end-to-end tests.
# AI implementation requirements
The AI must identify risk before writing tests, add tests alongside implementation, include failure-path coverage, and never mark work complete because only the happy path passes.
