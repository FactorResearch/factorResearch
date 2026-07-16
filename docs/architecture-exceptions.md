# Architecture Exception Register

This register is the only supported process for a justified deviation from
`docs/architecture.md`. Reviewers reject undocumented suppressions.

## Required record

```text
ID:
Status: proposed | approved | removed
Scope (files and dependency):
Reason no safe incremental alternative exists:
Risk and affected behavior:
Owner:
Containment and tests:
Removal trigger:
Target issue/date:
Approver:
```

## Resolved legacy baseline

### ARCH-001 — Presentation-owned analysis orchestration

- Status: removed by Issue 077
- Scope: `codes/app_modules/analysis.py` imports calculation models while it
  prepares analysis UI output.
- Risk: presentation and calculation changes can become coupled.
- Owner: application architecture maintainers
- Resolution: the workflow moved to `codes/services/stock_analysis.py`; all
  presentation, scheduler, worker, and test consumers now use the application
  service. The gate has no presentation-domain exception for this workflow.

### ARCH-002 — Universe module owns HTTP retrieval

- Status: removed by Issue 077
- Scope: `codes/engine/universe.py` performs a direct HTTP request.
- Risk: orchestration depends on a concrete client and is harder to substitute.
- Owner: market-data maintainers
- Resolution: SEC HTTP and payload mapping moved to
  `codes.data.providers.sec_universe.SecTickerUniverseAdapter` behind the
  `TickerUniverseReader` port. The direct-HTTP allowlist entry was removed.

### ARCH-003 — Framework session in analytics service

- Status: removed by Issue 077
- Scope: `codes/services/product_analytics.py` reads Flask request/session state.
- Risk: analytics policy is difficult to run outside a web request.
- Owner: analytics maintainers
- Resolution: Flask request/session access moved to
  `codes.app_modules.analytics_context.FlaskAnalyticsContext` behind the
  `AnalyticsContext` port. The presentation composition root injects it, and CI
  now rejects Flask/Dash imports from all application-service modules.

There are no active architecture exceptions after the Issue 077 reference
migrations. Lower-risk inventory items remain debt, not approved boundary
exceptions, and are tracked in `docs/technical-debt-register.md`.
