# Legacy Architecture Migration Playbook

## Select a slice

Choose one consumer-visible workflow from `technical-debt-register.md`. Rank it
by financial/business criticality, change frequency, complexity, coupling, and
test protection. Do not combine unrelated cleanup or formula changes.

## Protect behavior first

1. Identify all callers, jobs, persistence effects, cache keys, units, errors,
   nullability, freshness, and fallback behavior.
2. Add characterization tests at the current seam.
3. For calculations, add representative golden inputs/outputs and document any
   intentional formula change separately.
4. For provider/repository implementations, define one reusable contract suite.

## Establish the target boundary

- Put a narrow consumer-owned `Protocol` at the stable application/domain edge.
- Map vendor payloads and database rows in infrastructure adapters.
- Construct concrete adapters only in a composition root or compatibility seam
  scheduled for removal.
- Prefer composition and a cohesive module. Do not add an interface without a
  substitution, testing, ownership, or volatility reason.

## Migrate reversibly

1. Add the adapter/use case beside the legacy implementation.
2. Move one caller at a time; keep commits and PRs behavior-preserving.
3. Run old/new outputs against golden fixtures where both paths coexist.
4. Move workers and background jobs to the same application service.
5. Remove the legacy path and its architecture allowlist only after every caller
   is migrated.

## Verify and record

Run `./scripts/release-gate.sh`. Review the generated architecture and coverage
reports. Update the debt item with status, owner, remaining risk, removal
trigger, and relevant files. If a safe migration must be deferred, add a full
record to `architecture-exceptions.md`; an undocumented suppression is not
allowed.

## Pull-request review

Use `.github/PULL_REQUEST_TEMPLATE.md`. Confirm responsibility, extension point,
substitutability, interface width, inward dependency direction, error/unit/
null/freshness semantics, duplication, test boundary, and that the abstraction
is simpler than the coupling it replaces.
