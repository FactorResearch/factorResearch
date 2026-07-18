# Public API versioning and deprecation policy

## Scope

This policy governs the public HTTP API documented by `openapi.yaml`. The current
contract is `v1`, served below `/api/v1`. The OpenAPI document is the source of
truth for paths, operation identifiers, request parameters, response schemas,
authentication, and error envelopes.

## Compatible changes

The following changes are allowed within an active major version when the
existing behavior remains valid:

- Add an optional request parameter or request property.
- Add a response property that existing clients can ignore.
- Add a new endpoint, operation, or documented error code.
- Improve descriptions, examples, documentation, or observability without
  changing behavior.

New response fields must be safe for clients that reject unknown fields. A
change is not compatible merely because its JSON shape still parses: field
meaning, units, ordering, nullability, defaults, enum values, freshness, and
error semantics must remain stable.

## Breaking changes

Within an active major version, do not remove or rename an endpoint, operation,
parameter, response field, error status, or schema. Do not change a field's
meaning, type, format, nullability, required status, units, enum values,
authentication requirement, or retry semantics.

A breaking change requires a new major URL version, such as `/api/v2`, a new
OpenAPI contract and compatibility baseline, migration documentation, and a
rollout/rollback plan. The old version remains available during its support
window.

## Support windows and notice

- The current major version and the immediately preceding major version are
  supported.
- A preceding major version remains supported for at least 12 months after the
  successor reaches stable release.
- A deprecation notice must be published at least 6 months before planned
  removal, except for an urgent security or legal removal. Exceptions require
  an incident or security record and an explicit migration path.
- Deprecation notices must identify the exact endpoint, parameter, field, or
  behavior; explain the impact; name the replacement; state the removal major
  version; and include the planned removal date when known.

The machine-readable policy is exposed in `openapi.yaml` under
`x-api-lifecycle`. The current v1 contract has no deprecated fields or
operations.

## Deprecation metadata

Any OpenAPI item marked `deprecated: true` must include an `x-deprecation`
object with non-empty `replacement`, `removal_version`, and `notice` values.
The notice is also emitted to client-facing API documentation. Runtime
deprecation headers (`Deprecation` and, when scheduled, `Sunset`) should be
added by the owning route when an operation is deprecated; those headers are
not a substitute for the OpenAPI metadata or migration guidance.

## Enforcement and release process

`tests/api/test_api_compatibility.py` compares the active OpenAPI document with
`tests/api/fixtures/openapi-v1-baseline.json`. It rejects removed operations,
responses, fields, or incompatible schema constraints and validates
deprecation metadata. The same check runs from `scripts/quality-gate.sh`.

When intentionally changing a major contract:

1. Add the new version and its OpenAPI document.
2. Keep the previous version and baseline unchanged.
3. Add migration and deprecation documentation.
4. Add compatibility tests for both supported versions.
5. Update the lifecycle metadata and obtain review from the API owner.

If a compatible change causes client failures, roll back the contract change
or restore the previous response shape before retrying the migration. Never
delete the previous baseline to make CI pass.
