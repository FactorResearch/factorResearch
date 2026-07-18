# Subscription pricing and entitlements (ISSUE_008)

`codes.services.pricing` is the single plan catalog. Billing routes, Stripe
checkout, webhook synchronization, and permission evaluation must resolve
plans through this catalog rather than comparing plan names throughout the
application.

## Entitlement model

- Free/trial users receive three lifetime company analyses and custom factor
  weights. Usage is persisted server-side and consumed atomically.
- Premium users receive unlimited analysis, custom weights, backtesting,
  portfolio analytics, screening, and export according to `capabilities.json`.
- Unknown, retired, or inactive plans fail closed to Free.
- Stripe active status alone is insufficient: a subscription must also carry a
  recognized configured price before it grants Premium entitlements.

## Billing lifecycle

Checkout and portal sessions are user-derived server-side and support an
optional idempotency key. Signed Stripe webhooks synchronize checkout,
subscription changes, cancellation, and payment failure into the local
subscription record. Repeated webhook delivery is safe because subscription
updates are upserts keyed by the user and provider identifiers.

Billing failures expose generic copy in every environment; exception type is
logged as diagnostic context without returning raw provider details. No
financial data migration or new dependency is introduced by ISSUE_008.
