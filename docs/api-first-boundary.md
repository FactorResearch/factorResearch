# API-first backend boundary

Factor Research treats Dash, Flask HTML pages, workers, and future public APIs as
delivery adapters. They may validate transport input, choose presentation, and call
application services under `codes/services`; they must not own business rules or
read/write PostgreSQL directly.

The initial workflow boundaries are:

- Analyze: `codes.services.stock_analysis`
- Portfolio: `codes.services.portfolio_service`
- Screener: `codes.services.screener_service`
- Account: `codes.services.account_service`
- Billing: `codes.services.billing_service` and `codes.services.permissions`

Only server-side services and their repository/provider adapters may access the
database, credentials, authorization decisions, validation policies, rate controls,
logging, or audit facilities. Browser clients must never connect directly to
PostgreSQL or receive database credentials. New UI callbacks and routes must use an
existing service boundary or introduce a narrow service operation with tests.

These modules intentionally provide stable use-case operations while legacy engines
and repositories are incrementally decomposed. API contracts and transport-neutral
response models are handled by ISSUE_060 and ISSUE_061; this boundary avoids
pre-empting those contracts.
