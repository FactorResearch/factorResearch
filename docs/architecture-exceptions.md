# Architecture Exception Register

This register is the source of truth for deliberate, temporary deviations from
the repository's enforced architecture boundaries. An exception records an
approved migration constraint; it does not permanently weaken the boundary or
silence an unexplained violation.

## Current register

There are no active architecture exceptions.

## When an exception is permitted

An exception may be added only when an enforced boundary cannot be restored in
the same change without creating greater delivery, availability, data-integrity,
or security risk. Convenience, schedule pressure, and avoiding a small refactor
are not sufficient reasons.

Before approval, the author must show that:

- the violation and affected boundary are precisely identified;
- compliant alternatives were evaluated and rejected with evidence;
- the exception has the narrowest practical code and time scope;
- compensating tests or operational controls limit the resulting risk; and
- an owner, tracking issue, and objective removal condition exist.

Security, privacy, billing, and tenant-isolation exceptions require explicit
review from the owner responsible for that boundary. An exception must never be
used to bypass a release-blocking vulnerability or conceal user-data exposure.

## Register entry format

Each exception is one third-level Markdown section. Its heading must contain a
stable identifier and a short description. The section must provide all of the
following fields:

- **Status:** `active` or `removed`.
- **Owner:** the accountable person or team.
- **Tracking issue:** a durable issue or decision-record link.
- **Affected paths:** the smallest explicit list of files or modules.
- **Boundary:** the architecture rule being violated.
- **Rationale:** why a compliant implementation is currently unsafe or
  impractical.
- **Alternatives considered:** the compliant options evaluated and why they do
  not work yet.
- **Compensating controls:** tests, monitoring, isolation, or review that limits
  risk while the exception exists.
- **Removal condition:** an observable condition that makes deletion mandatory.
- **Review deadline:** an ISO 8601 date no more than 90 days after approval.
- **Approved by:** the reviewer who accepted the temporary risk.

Do not add placeholder entries. A proposed exception remains a pull-request
discussion until every required field is complete and approval is recorded.

## Lifecycle

Active exceptions must be reviewed by their deadline and whenever affected code
changes. A review may remove the exception or approve a new deadline with an
updated rationale; silently extending a date is prohibited.

When the code becomes compliant, keep the historical entry, set its status to
`removed`, and record the removal pull request and date. Git history remains the
authoritative change log; the retained entry explains why the deviation once
existed and proves that it no longer authorizes new violations.

## CI enforcement

`scripts/architecture-report.py --check` reads this register during the release
gate. Every third-level section not containing `Status: removed` is treated as an
active exception and fails the protected architecture check. The register must
therefore contain no active entry when a release is approved.

Boundary allowlists in code are not substitutes for this register. Any temporary
allowlist entry must reference its registered exception, and both must be removed
in the same change when the removal condition is met.
