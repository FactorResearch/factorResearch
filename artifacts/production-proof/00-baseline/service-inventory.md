# Service and Dependency Inventory

## Deployable Processes

| Process | Entry point | Purpose | State/dependencies |
|---|---|---|---|
| Release migration | `python -m codes.data.migrate` | Create/upgrade market, user, and snapshot schemas | All PostgreSQL DSNs |
| Web | `gunicorn ... codes.app:server` | Dash/Flask UI, routes, callbacks, startup cache load | PostgreSQL, Redis, providers |
| SEC refresh worker | `codes/workers/sec_refresh_worker.py` | Refresh persisted SEC facts | SEC, market DB |
| Canada ingestion worker | `codes/workers/canada_ingest_worker.py` | Validate/import Canada data | Source files, market DB |
| Analysis job consumer | `codes.services.analysis_jobs.work_forever` | Deferred and refresh analyses | Redis queue, providers, DB |

The analysis consumer is currently launched by in-process maintenance. Its production process ownership is an open Phase 3 risk because multiple web workers can create duplicate consumers/schedulers.

## Persistent and Shared State

| Store | Data | Availability policy |
|---|---|---|
| Market PostgreSQL | SEC facts, analyses, factors, snapshots, metadata, logos, screener rows | Required for core analysis and persisted results |
| User PostgreSQL | subscriptions, usage, weights, portfolios/account-linked state | Required for authenticated/private operations |
| Analytics PostgreSQL | events and public/custom snapshot records when separately configured | Optional analytics; snapshot routes require configured storage |
| Redis | sessions/rate-limit consistency, analysis jobs, singleflight, shared chart/progress cache | Required for horizontally consistent production behavior |
| Filesystem cache | disposable public/provider payloads and locks | Optional optimization; must tolerate absence/read-only failure |

## External Dependencies

| Dependency | Capability | Data exchanged | Failure mode |
|---|---|---|---|
| SEC EDGAR | filings, facts, issuer universe | ticker/CIK requests; public filings returned | cached/stored data where valid; provider error otherwise |
| Finnhub | live quote, splits, revisions | ticker and API credential | fallback/circuit breaker |
| Tiingo | historical/EOD prices | ticker and API credential | fallback/circuit breaker |
| Alpha Vantage | final price fallback | ticker and API credential | declared unavailable when exhausted |
| Logo.dev | company logos | company name/domain-like identifier | initials/fallback identity |
| Auth0 | authentication | OAuth metadata and account identity | authentication unavailable; existing-session policy tested in Phase 3 |
| Stripe | checkout, portal, subscription events | user/price/customer metadata | billing unavailable; core analysis isolation required |
| SMTP | waitlist/transactional mail | recipient and message | queue/log failure without exposing credentials |
| PostHog/Clarity/Sentry | optional telemetry | consented/redacted events/errors | non-blocking and opt-out enforced |

## Concurrency Owners

| Component | Current bound |
|---|---:|
| Provider gateway executor | 16 threads/process |
| Per-provider semaphore | 4 default, environment override |
| Local analysis jobs | 2 threads/process |
| Product analytics | 2 threads/process |
| Co-momentum | configured by `COMOMENTUM_WORKERS` |
| Market/user DB pools | 5 connections/DSN/process default |
| Analytics DB pool | 2 connections/process default |
| Snapshot DB pool | 3 connections/DSN/process default |

Total connection and thread budgets must multiply these values by Gunicorn process count during Phase 2.

## Configuration Classes

- **Required production security:** `FLASK_ENV`, `FLASK_SECRET_KEY`, `ENCRYPTION_KEY`, `TRUSTED_HOSTS`, authentication configuration, `RATELIMIT_STORAGE_URI`, `REDIS_URL`.
- **Required data:** `DATABASE_MARKET_URL`, `DATABASE_USERS_URL`, configured analytics/snapshot DSNs, `SEC_USER_AGENT`.
- **Provider credentials:** `FINNHUB_API_KEY`, `TIINGO_API_KEY`, `AV_API_KEY`, optional licensed-country credentials.
- **Billing:** `STRIPE_SECRET_KEY`, price ID, webhook secret, public base URL.
- **Optional telemetry/email:** PostHog, Clarity, Sentry, SMTP variables.
- **Capacity controls:** database pool sizes, provider timeout/circuit/concurrency, analysis refresh/precompute, co-momentum workers.

Secret values are never evidence artifacts. Phase 1 must validate presence and shape without printing values.
