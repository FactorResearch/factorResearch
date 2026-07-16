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

Public client operations must use the versioned contract described in
`docs/public-api-v1.md` and `openapi.yaml`. Existing browser HTML, provider
callback, telemetry, and internal operations endpoints are not public client
contracts.

`codes/domain/responses.py` is the response boundary shared by API and web
delivery adapters. Its immutable models cover analyses, factors, portfolios,
jobs, users, subscriptions, errors, and capabilities. Application services map
legacy engine and repository results into these models before delivery; adapters
then choose their own HTTP envelope, formatting, components, colors, and layout.

The domain serialization removes presentation keys recursively. The Dash adapter
maps semantic verdict and regime codes to visual treatment locally, while the API
serializes the same response models into the versioned OpenAPI contract.
