# Analyze and Portfolio section fault tolerance

This reliability boundary keeps essential page content usable when an optional
financial model, chart, or cached enrichment section fails.

## Analyze

`codes/app_modules/analysis_ui.py` wraps optional model-card renderers with
`_safe_analysis_component`. A renderer exception becomes an accessible local
error panel with a stable section retry target and technical diagnostic ID;
the overview and sibling model sections continue to render. Financial
calculations remain in their existing services and are not duplicated in the
presentation layer.

Historical charts are deferred and already have their own loading, empty,
error, and retry callback. A chart failure therefore does not replace the
analysis summary or model cards.

## Portfolio

Holdings and user-entered values are essential. Cached analysis enrichment is
optional and is treated as unavailable when its repository/provider read fails;
the holdings table and portfolio controls still render. Simulation work is
submitted as an owner-scoped, deduplicated background job with bounded retries,
progress, cancellation, and a local retryable failure state.

## Failure contract

- Missing or failed optional data is unavailable/partial, never numeric zero.
- Successful sibling sections remain visible.
- A section reaches a terminal error state after bounded recovery attempts; no
  section may remain indefinitely loading.
- Retry and cancellation controls are scoped to the affected operation.
- Technical exception types are diagnostics only and are not shown as the
  primary user message.

The regression coverage is in `tests/test_issue_042_fault_tolerance.py`.
