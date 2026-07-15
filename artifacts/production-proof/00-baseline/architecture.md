# Production Architecture and Trust Boundaries

## Runtime Topology

```text
Browser / mobile browser
        |
        | HTTPS through hosting proxy
        v
Gunicorn -> Dash/Flask web process
  |  |  |  |\
  |  |  |  +--> Redis: sessions, rate limits, jobs, singleflight, chart data
  |  |  +-----> Market PostgreSQL: facts, analyses, factors, logos, projections
  |  +--------> User PostgreSQL: accounts, portfolios, usage, subscriptions
  +-----------> Analytics PostgreSQL: product events and public snapshots
        |
        +--> SEC EDGAR, Finnhub, Tiingo, Alpha Vantage, Logo.dev
        +--> Auth0, Stripe, SMTP, PostHog, Clarity, Sentry

In-process maintenance -> Redis analysis queue -> analysis worker loop
Country ingestion workers -> normalized market PostgreSQL records
```

The current `Procfile` starts migrations as the release command and Gunicorn as the web command. Background analysis maintenance currently starts from application startup; Phase 3 must prove behavior with multiple Gunicorn workers and determine whether it must become a separately scaled process.

## Primary Data Flows

1. **Stock analysis:** ticker input -> validation/rate limit -> SEC and price providers -> normalized facts -> versioned models -> market database/cache -> UI and optional background enrichment.
2. **Portfolio:** authenticated/session identity -> user database/cache -> market history -> simulation -> browser charts. Holdings are private user data.
3. **Billing:** authenticated identity -> Stripe checkout/portal -> signed webhook -> user subscription state. Stripe is authoritative for payment events.
4. **Authentication:** browser -> Auth0 OAuth/JWT -> server-side session -> authorization checks. Auth0 credentials and session secrets remain server-side.
5. **Analytics:** consent/opt-out gate -> asynchronous event write and configured analytics vendors. Optional telemetry must not block analysis.
6. **Country ingestion:** licensed/regulatory source -> ingestion worker -> provenance/quality validation -> market-generic tables -> screener projection.

## Trust Boundaries

| Boundary | Untrusted input | Required control |
|---|---|---|
| Browser to application | Forms, callbacks, cookies, route/query values | Authentication, authorization, CSRF, validation, sanitization, rate limits |
| Reverse proxy to Flask | Host, scheme, forwarding headers, client IP | Explicit trusted proxies/hosts and HTTPS enforcement |
| Application to providers | Remote JSON/HTML, timeouts, schema drift | Timeouts, bounded concurrency, circuit breakers, normalization, provenance |
| Application to PostgreSQL | Dynamic values and transactions | Parameterized SQL, least privilege, bounded pools, migration ownership |
| Application to Redis | Shared cache/job/session state | Authentication/TLS, namespaced keys, TTLs, outage policy |
| Stripe to webhook | Raw body, signature, duplicate/reordered events | Signature verification, idempotency, state reconciliation |
| Auth0 to application | Tokens and rotating signing keys | Issuer/audience/state/nonce validation and bounded JWKS retrieval |
| Build system to production | Artifact, dependencies, migrations | Immutable artifact, SBOM, scans, approvals, rollback |

## Data Classification

| Class | Examples | Storage/handling |
|---|---|---|
| Public market data | filings, prices, scores, public snapshots | Provenance and license controls; cacheable |
| Private user data | portfolios, holdings, account identifiers | Tenant isolation, encryption, retention/deletion controls |
| Payment metadata | Stripe IDs, plan/status | No card data stored; restricted user database access |
| Credentials | API keys, DB URLs, session/encryption secrets | Secret manager only; never logs/client/source |
| Operational telemetry | IP-derived rate keys, events, errors, traces | Minimize, redact, consent where required, expire by policy |

## Authoritative State

- PostgreSQL is authoritative for market, user, subscription, and durable analytics records.
- Stripe is authoritative for payment settlement; local state is reconciled from signed events/API reads.
- Redis and filesystem caches are disposable unless a specific queue durability contract states otherwise.
- External filings and licensed provider records are authoritative source inputs; derived model results must retain source and algorithm versions.
