# CenvarnAI Context

This is the single authoritative context file for AI work in this repository.
Load this file before coding. It consolidates project memory, Ponytail simplicity,
Caveman communication, and the Engineering, Design, Testing, and Security
standards adapted from `FactorResearch/agency-agents`. Other Markdown files are
product documentation, audit evidence, or optional tool references; they are not
required to understand how to work here.

## Product And Current Stage

Cenvarnis an early-development fundamental investing, stock analysis,
screener, and portfolio analytics platform. It runs locally on `localhost` unless
the user explicitly identifies another environment. It is not a registered
investment adviser and must not present model output as personalized advice.

The product goal is fast, trustworthy analysis: a user should be able to open the
app between meetings or while travelling, analyze several stocks quickly, see the
important conclusion immediately, and reveal detail only when wanted.

The application uses Python, Flask, Dash, PostgreSQL, Redis, SCSS, and limited
client-side JavaScript. Financial calculations, authentication, billing, provider
access, SEC normalization, portfolio simulation, and authoritative persistence
remain server-side. Client code may handle presentation, interaction, and safe
derived display work, but must not duplicate trusted financial-model logic.

## Priority Order

When priorities conflict, use this order:

1. Security, privacy, and prevention of data loss or cross-user access
2. Mathematical and financial-model correctness
3. Reproducibility, provenance, and backward compatibility
4. Accessibility and user-task completion
5. Test evidence and operational reliability
6. Performance and resource efficiency
7. Simplicity and maintainability
8. Visual polish

Shorter code is preferred only when it preserves every higher priority. Never
simplify away validation, authorization, accessibility, error handling that
protects data, observability required for recovery, or explicitly requested work.

## Working Method

Before editing:

1. Restate the requested outcome and identify the user-visible behavior.
2. Inspect the actual code path, existing tests, callers, persistence, and failure
   boundaries. Do not assume the report identifies the root cause.
3. Reproduce or otherwise prove the issue exists.
4. Check the worktree and preserve unrelated user changes.
5. Find existing helpers, patterns, native features, and dependencies before
   creating anything.
6. Explain the root cause and choose the smallest correct change at the shared
   boundary where all affected callers pass.
7. For substantial work, split it into independently testable phases.

During implementation:

1. Make one coherent change at a time.
2. Add the smallest meaningful regression test with each nontrivial change.
3. Run focused checks first, then the full release gate before declaring success.
4. Reinspect the diff and original request after tests pass; loop until no stated
   requirement or adjacent regression was missed.
5. Push only verified checkpoints when the user requests phase-by-phase delivery.

Do not stop at a plan when implementation was requested. Continue through code,
tests, runtime verification, documentation, and a concise outcome unless blocked
by required user input or external infrastructure.

## Ponytail Simplicity Standard

Be a lazy senior engineer: efficient, not careless. The best code is code that
does not need to exist. After understanding the complete path, stop at the first
rung that fully holds:

1. Does this need to exist? Skip speculative work.
2. Does the repository already solve it? Reuse that implementation.
3. Does the standard library solve it? Use it.
4. Does the browser, database, framework, CSS, HTTP, or platform solve it natively?
5. Does an already-installed dependency solve it?
6. Can direct, readable code solve it without a new abstraction?
7. Only then add the minimum new implementation.

Rules:

- Root-cause fixes beat symptom patches. One shared guard is better than repeated
  guards in every caller.
- Delete dead behavior before adding replacement layers.
- Prefer boring, explicit code over clever compression.
- Use the fewest files and concepts that keep ownership clear.
- Do not add interfaces with one implementation, factories with one product,
  wrappers that only delegate, config nobody changes, speculative extension
  points, or dependencies for a few clear lines.
- A one-line rewrite is good only when it remains readable, correct on edge cases,
  and easier to debug. Never optimize for line count alone.
- Do not split large files merely to make files smaller. Split only when behavior,
  ownership, change cadence, or test boundaries become clearer.
- Do not consolidate similar financial-model helpers when thresholds, accepted
  records, missing-data semantics, or outputs differ. Consolidate exact behavior.
- Mark a deliberate shortcut only when it has a real ceiling, using
  `ponytail: <ceiling>, <specific trigger/upgrade path>`.
- No speculative refactoring. Refactor when requested or when it is the smallest
  safe route to the required fix.

Over-engineering reviews use these labels:

- `delete`: dead or speculative behavior; replace with nothing.
- `stdlib`: replace custom code with the named standard-library feature.
- `native`: replace code/dependency with a platform feature.
- `yagni`: remove unused abstraction or flexibility.
- `shrink`: same behavior with materially simpler readable code.

Complexity findings are separate from correctness, security, and performance
findings. Never recommend deleting a protective control as a simplification.

## Engineering Standards

### Python And Service Code

- Keep modules cohesive and dependencies directional.
- Use explicit data contracts at provider, database, queue, API, and model
  boundaries.
- Validate once at each trust boundary; do not repeatedly sanitize trusted
  internal values.
- Use parameterized SQL. Dynamic identifiers require fixed allowlists.
- Keep database transactions short and explicit.
- Use bounded, lazy, fork-aware connection pools with health visibility.
- Do not run schema DDL, historical migration, or network initialization on hot
  read paths. Migrations belong to the release phase.
- Bound every process cache, lock registry, executor queue, retry loop, and external
  call. Expired entries must be evicted, not merely ignored.
- A timeout does not stop a Python worker thread. Concurrency permits remain owned
  until timed-out work actually exits.
- Avoid broad exception swallowing. Catch expected errors, preserve a useful
  signal, and fail securely without leaking secrets or internals.
- Use structured, redacted logs and correlation IDs. Never log tokens, cookies,
  secrets, connection strings, customer financial records, or unnecessary PII.
- Prefer bulk database/provider operations over N+1 loops. Add query-count tests
  for backtests, portfolios, and universe operations.
- Preserve public APIs, CLI behavior, output schemas, model versions, and stored
  data unless the task explicitly changes them.

### JavaScript And Client Code

- Use JavaScript only where browser execution reduces latency or improves
  interaction without duplicating trusted server logic.
- Prefer native DOM/browser APIs and CSS over libraries.
- Keep event ownership explicit; avoid global listeners and repeated callback
  registration.
- Never insert untrusted HTML. Use text nodes or safe framework children.
- Reserve chart dimensions before rendering to prevent layout shift.
- Draw expensive charts only after the user expands them; avoid doing hidden work.
- Handle loading, stale, empty, error, retry, and offline states intentionally.
- Keep client payloads bounded and versioned.

### Performance

- Measure before optimizing. Record baseline, workload, environment, p50/p95/p99,
  error rate, throughput, and resource saturation.
- Optimize network/database round trips and repeated model/provider work before
  micro-optimizing Python syntax.
- Reuse persisted analysis for already-analyzed stocks; do not recalculate unchanged
  authoritative inputs on every page load.
- Use singleflight, versioned bounded caches, background workers, durable queues,
  and idempotent persistence where they measurably reduce duplicate work.
- Keep web workers free of scheduled/background maintenance in production.
- Design graceful shutdown so workers stop accepting work, preserve unacknowledged
  jobs, and recover them idempotently.
- Localhost benchmarks do not prove production capacity because client, server,
  database, and network may share one machine.
- Never move financial models to JavaScript merely to claim client offloading.

## Financial Model Standards

Correctness outranks elegance. Every model must declare required inputs, missing
data behavior, output schema, version, provenance, and tests.

### Shared Rules

- Never convert missing data to a misleading zero.
- Normalize partial weighted scores by available weight only when the methodology
  explicitly permits partial scoring.
- Align annual comparisons to fiscal periods approximately one year apart; never
  compare arbitrary adjacent statements.
- Guard `None`, NaN, infinity, zero denominators, negative values where undefined,
  stale filings, split-adjustment differences, and restatements.
- Keep source/provider and calculation timestamps distinct.
- Persist model and data versions with results.
- Golden fixtures, invariants, boundary cases, and cross-period consistency are
  required for material model changes.

### Model-Specific Rules

- Graham: dividend years must be consecutive; non-continuous history does not
  qualify.
- Piotroski: year-over-year signals use aligned fiscal periods.
- Altman: missing components must not artificially depress the score; normalize
  permissible partial scores by available weight.
- Greenblatt: Net Working Capital excludes cash and equivalents; earnings yield is
  enterprise-value based.
- Portfolio volatility: use the covariance matrix; never assume assets are
  independent.
- Monte Carlo: use geometric drift `mu_geo = mu_arith - sigma^2 / 2`.
- Sortino: downside deviation uses all observations `N`, not only downside count.

### New Model Integration

Every new model or engine must:

1. Register a stable contract and version.
2. Join the primary analysis pipeline and persisted result schema.
3. Render in the correct UI section without mixing unrelated domains. Accounting
   models stay in Accounting, not Overview.
4. Work for newly analyzed stocks.
5. Backfill or enqueue idempotent refreshes for every already-analyzed stock in the
   database. A model is incomplete if existing stocks never receive its output.
6. Avoid recalculating unchanged shared inputs.
7. Add unit, integration, persistence, existing-stock backfill, and UI-presence
   tests.
8. Update the model manifest and roadmap/release documentation.

Do not run an expensive model with no UI, API, persistence consumer, or explicit
background purpose. Remove unused computation or expose the result intentionally.

## Product And Design Standards

### Information Architecture

- Keep Overview and Accounting separate.
- Each section is short, informative, and scannable. Users should understand the
  headline quickly without losing access to supporting information.
- Landing state shows highlights only. Progressive disclosure reveals detail,
  charts, methodology, and secondary metrics on demand.
- Do not cram cards, graphs, pills, and tiny text into one viewport.
- Information may be hidden behind a clearly named action, but not buried so users
  cannot discover it.
- Design for known future expansion before adding more cards.
- Quick Peek must provide a useful decision without leaving the screener and must
  never require scrolling: company identity, updated date, composite, verdict,
  price, market cap, moat, and full-analysis action.
- Navigation must maintain location: sticky main navigation where appropriate,
  active section indication, stable jump navigation, and no scroll jumping.

### Visual Direction

- Minimal and premium, not generic dashboard clutter.
- Light and dark modes are equal products; neither may be an afterthought.
- Use intentional typography, restrained hierarchy, subtle depth, and limited
  meaningful motion.
- Avoid excessive round corners, default framework styling, purple bias, flat
  unstructured backgrounds, and interchangeable card grids.
- Company logos may be used through the configured provider/cache. Provide robust
  monogram fallbacks, accessible names, bounded dimensions, and no layout shift.
- Every component state must match the site language: inputs, dropdowns, badges,
  delete actions, accordions, charts, legal dialogs, portfolio controls, and
  navigation.

### SCSS Architecture

- SCSS is the source of truth; generated CSS must match it exactly.
- Keep colors in a color/token partial. Do not scatter literal theme colors.
- Use variables, functions, mixins, partials, and imports where they reduce real
  repetition and clarify ownership.
- All media queries originate as mixins in `assets/_media.scss`; component files
  call those mixins and contain no direct ad hoc media queries.
- Nest child selectors inside the parent component so structure is readable.
- Keep one coherent partial per component/domain; do not spread one component's
  styles across unrelated files or create tiny single-rule partials.
- Reuse structure, not arbitrary old colors or font sizes.
- Compile with the repository command and no source map when updating tracked CSS.
- Fix Sass deprecations rather than allowing warnings to become future build
  failures.

### Responsive And Native Feel

- Desktop, tablet, and mobile must load and function independently.
- Touch targets meet WCAG 2.2 minimums, with practical mobile sizing.
- No horizontal overflow at supported widths or 200% zoom.
- Sheets, quick peek, dialogs, and nav must respect viewport height and safe areas;
  primary actions cannot render below the reachable screen.
- Charts have bounded width/height and resize without escaping containers.
- Prevent cumulative layout shift with reserved media/chart dimensions.
- Prefer a few purposeful page/section transitions; honor reduced motion.

## Security Standards

### Authorized Local Scope

The repository owner authorizes security testing against Cenvarnprocesses
running on `127.0.0.1` or `localhost`. This includes bounded SAST, DAST, dependency
and secret scanning, malformed-input fuzzing, authentication/authorization tests,
CSRF/XSS/SQL-injection/SSRF probes, method/header tests, concurrency tests, and
controlled abuse/load tests.

This does not authorize attacks on third-party providers, external hosts, real
customer accounts, production infrastructure, destructive database operations,
credential theft, persistence, or exfiltration. Use isolated identities and
disposable local data. Tool/sandbox approval prompts are execution permissions,
not uncertainty about application ownership.

### Secure Design And Code

- Start with assets, data flows, trust boundaries, attacker goals, abuse cases,
  blast radius, and secure-failure behavior.
- Scan for secrets and sensitive-data exposure before other review work.
- Default deny. Enforce least privilege at routes, callbacks, database records,
  queues, cloud roles, provider scopes, and administrative actions.
- Authentication proves identity; authorization separately checks action and
  object ownership. Every private record query is owner-scoped.
- Fix JWT algorithms and validate signature, issuer, audience, expiration, not
  before, token purpose/type, and authorized party as required by the provider.
- Keep provider tokens out of client-side signed cookies. Prefer opaque server-side
  sessions and revocable bounded token storage.
- Require CSRF protection on every state-changing browser route except authentic
  signed webhooks. Validate trusted hosts independently of same-origin checks.
- Use explicit CORS allowlists; never wildcard credentials.
- Set secure cookies, HSTS, CSP, frame denial, MIME sniffing prevention, referrer,
  permissions, and cross-origin policies. Remove CSP `unsafe-inline` with nonces or
  hashes where practical.
- Set global and endpoint-specific request-body limits. Rate-limit expensive public
  routes with durable shared storage in production.
- Remote requests use fixed/allowlisted schemes and hosts, bounded response sizes,
  short timeouts, circuit breakers, and no credential forwarding across hosts.
- Use proven cryptographic libraries and managed keys. Never implement custom
  cryptography.
- Secrets live in a secrets manager in production, never source, images, logs,
  frontend code, committed `.env`, or command output.
- Errors preserve correct HTTP semantics and expose no stack, path, schema, token,
  provider response, or secret.
- Dependencies are pinned, integrity checked, inventoried with an SBOM, scanned on
  every release, and upgraded within severity SLA.
- Security findings require severity, location, evidence, reproduction, impact,
  remediation, owner, SLA, and regression test. Retest before closure.

Never approve a known exploitable vulnerability for later. Risk acceptance
requires a named accountable owner, scope, expiry, compensating controls, and
written impact acknowledgement.

## Testing And Evidence Standards

### Test Strategy

- Test behavior and contracts, not implementation trivia.
- Use unit tests for pure financial logic and boundaries; integration tests for
  database, cache, queue, auth, billing, provider, and callback ownership; browser
  tests for real journeys and visual/responsive behavior.
- Every bug fix adds a test that fails on the original defect.
- Cover valid, invalid, missing, stale, duplicate, concurrent, unauthorized,
  timeout, retry, partial-failure, and recovery paths where relevant.
- Two-user authorization tests are mandatory for private data.
- Use hermetic tests: no undeclared live network, clock, randomness, filesystem,
  provider, or local database dependency.
- Flaky tests are defects. Record seed, environment, timing, and evidence needed to
  reproduce.

### API And Security Testing

- Inventory every route/method and expected auth, entitlement, ownership, body
  limit, rate limit, content type, and error schema.
- Test malformed JSON/form/multipart bodies, duplicate parameters, oversized
  values, Unicode, traversal, injection, hostile headers, unsupported methods,
  replay, concurrency, and idempotency.
- Verify unknown hosts, wrong origins, wrong JWT claims, expired/revoked sessions,
  invalid webhook signatures, and cross-user identifiers fail before business
  logic.
- A scanner warning is not a confirmed vulnerability until reachability,
  exploitability, and business impact are checked. Record false positives and
  mitigations.

### Accessibility And UX Evidence

- Target WCAG 2.2 AA.
- Automated axe scans are baseline only, never certification.
- Test keyboard order, visible focus, skip/navigation behavior, dialogs, tabs,
  accordions, dropdowns, dynamic announcements, charts, errors, and loading states.
- Manually test VoiceOver, NVDA, and TalkBack on supported devices before public
  certification.
- Test light/dark, forced colors, reduced motion, 200% zoom, text spacing, mobile
  orientations, touch targets, and horizontal overflow.
- Capture screenshots or machine-readable evidence for UI claims. Do not declare
  visual success from source inspection alone.

### Performance And Reliability Evidence

- Test baseline, load, stress, spike, and soak against a production-equivalent
  topology before certification.
- Include warm/cold analysis, cached/uncached stocks, screener, portfolio,
  authentication, billing, queues, database pools, provider quotas, and slow/error
  dependencies.
- Fault tests cover PostgreSQL, Redis, providers, disk/cache, worker death, queue
  interruption, malformed data, clock/timeouts, and partial writes.
- A backup is not proven until restored. Record RPO/RTO, row/constraint checks,
  recent writes, application journeys, and cleanup.

### Evidence And Release Decisions

- Run focused tests, full `scripts/release-gate.sh`, security scans, and
  `git diff --check` before completion.
- Preserve concise machine-readable evidence when practical.
- Never report a pass without the command/result or direct runtime observation.
- Default production-readiness result is `NEEDS WORK` until overwhelming evidence
  supports approval.
- Automated tests and documentation do not substitute for external penetration
  testing, production-scale drills, legal/licensing review, physical-device and
  assistive-technology testing, or timed human incident exercises.

## Operations And Production Proof

- Release configuration fails closed before migrations or startup.
- Use expand/migrate/contract database changes; no destructive rollback claims
  without compatibility or tested restore.
- Deploy immutable artifacts through canary/staged traffic with numeric rollback
  criteria.
- Telemetry covers request RED metrics, analysis stages, providers/circuits,
  caches, database pools, Redis, queues/dead letters, model failures, auth, and
  billing. Missing telemetry is an incident.
- Alerts have severity, owner, threshold, and executable runbook.
- Maintain incident command, evidence preservation, customer/legal/vendor
  escalation, and blameless corrective actions.
- Production certification requires capacity, reliability, model integrity,
  security, privacy/legal, observability, recovery, deployment, accessibility,
  and incident sign-off. Code health alone is not certification.

## Git, Branch, And File Safety

- The worktree may contain user changes. Never revert, overwrite, stage, or commit
  unrelated work.
- Do not use destructive Git commands. Do not amend unless explicitly requested.
- Use `rg`/`rg --files` for search and `apply_patch` for manual edits.
- Keep edits ASCII unless an existing file and clear need justify Unicode.
- Do not commit secrets, generated local evidence containing sensitive data, cache,
  screenshots not requested for evidence, or database exports.
- Roadmap/future-version work never lands directly on `main`. Create a dedicated
  branch named for the version or phase.
- Keep roadmap branches current with `main`; stop and ask before resolving a merge
  conflict caused by synchronization.
- Scope commits to one verified phase. Do not push until focused/full checks pass
  when the user requests checkpoint delivery.
- `roadMap.md`/`roadmap.md` is intentionally untracked and ignored. Do not add it to
  Git unless the user explicitly reverses that decision.

## Communication And Delegation

Communicate like a concise senior engineer:

- State facts, decisions, risks, and next action. Remove praise, filler, repeated
  acknowledgement, and speculative narration.
- Preserve exact technical names, commands, paths, API symbols, and error text.
- Use short sentences or fragments when unambiguous. Use full explicit language
  for security warnings, irreversible actions, and ordered recovery steps.
- Do not dump raw logs; quote the decisive lines and summarize the rest.
- For reviews, findings come first, ordered by severity with file/line references.
- For completed changes, report outcome, verification, and real residual risk.
- User-requested reports and explanations may be detailed; concision must not
  remove required evidence.

Delegate only when it saves context or parallelizes independent work:

- Investigator: locate flows, callers, boundaries, and tests; no edits.
- Builder: one narrow implementation spanning roughly one or two files.
- Reviewer: inspect a completed diff for correctness, security, regression, and
  missing tests.
- Keep architecture, cross-cutting edits, conflict resolution, final integration,
  and user communication in the main thread.
- Give delegates exact scope, constraints, and expected output. Verify their work;
  delegation does not transfer accountability.

## Required Change Report

For material changes, provide only the useful parts of this structure:

### Files Modified

- File and reason.

### Logic Change

- Old behavior and new behavior.

### Verification

- Focused tests, full gate, runtime/browser/security checks as applicable.

### Risks

- Assumptions, untested external conditions, migration/compatibility concerns, and
  follow-up evidence still required.

Do not force this structure onto trivial one-line tasks.

## Definition Of Done

Work is complete only when:

- The requested behavior is implemented at the root cause.
- Existing stocks/data remain compatible, including required new-model backfill.
- Security, privacy, accessibility, and failure boundaries are preserved.
- Focused tests and the complete applicable gate pass.
- Generated assets match their source.
- The diff contains no accidental or unrelated changes.
- Runtime/UI behavior is directly verified when source tests cannot prove it.
- Documentation, manifests, roadmap/release evidence, and migrations are updated
  when the behavior or operating contract changed.
- The final response states remaining risks honestly.

If external proof is missing, implementation may be complete while production
certification remains blocked. Never confuse those states.

## Design Documentation

Visual implementation does not come from this file.

Before implementing any UI work the AI MUST read

design/README.md

Follow the reading order documented there.

Never redesign.

Never simplify.

Never remove information.

## Notion source synchronization

The connected Notion workspace is the detailed source of truth for current
engineering and design standards. The repository mirrors are the execution layer.
For UI work, load the Notion **New UI Design Implementation Plan**, its attached
prototype, and the applicable standards listed by the workspace page before
editing code. If local Markdown conflicts with Notion, update the local mirror
before implementation and record the synchronization in the task report.

Implement exactly as documented.
