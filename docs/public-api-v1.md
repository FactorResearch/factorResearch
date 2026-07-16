# Public API v1

`/api/v1` is the only public client contract. Browser-oriented HTML routes,
OAuth callbacks, payment-provider webhooks, telemetry collectors, and internal
operations routes are delivery or integration endpoints, not public client APIs.

The source of truth is `openapi.yaml`, also served at
`/api/v1/openapi.yaml`. It defines request parameters, response fields,
authentication, pagination, and the stable error envelope. The document is JSON
encoded YAML 1.2 so build tooling can validate it without a YAML dependency.

Public responses serialize the immutable domain response models in
`codes/domain/responses.py`. Analysis responses include semantic factor and
capability collections; they never include CSS classes, colors, component names,
icons, or layout choices. The web renderer consumes the same domain model and
owns those presentation decisions locally.

Public responses are allow-listed projections of application-service results.
Adapters must not return raw database rows, provider payloads, exception text,
credentials, or uncontracted fields. New public endpoints must be added below an
explicit API version, documented before release, and covered by a response
contract test.

Authenticated operations accept a provider-verified bearer JWT or the secure web
session cookie. Collection operations use one-based `page` and `page_size`
parameters; `page_size` is capped at 100. Errors always contain a stable machine
code, a safe user-facing message, the API version, and request ID.

`codes/api/schemas.py` provides checked Python transport types corresponding to
the OpenAPI component schemas. These types remain transport-only; the reusable
domain response models are independent of Flask, Dash, database, and provider
dependencies.
