# Synthetic Journeys

Run from outside the production network with dedicated, least-privilege test identities. Never use real customer portfolios or payment instruments.

| Journey | Interval | Success condition | Maximum duration |
|---|---:|---|---:|
| Public health | 1 minute | health endpoint returns expected version and dependencies | 2 seconds |
| Screener | 5 minutes | first page renders nonempty or an explicit empty state | 5 seconds |
| Cached analysis | 5 minutes | known ticker returns a complete snapshot and model version | 5 seconds |
| Cold analysis | 15 minutes | queued analysis completes without dead letter | 60 seconds |
| Portfolio | 15 minutes | synthetic holding can be read and simulation controls render | 10 seconds |
| Authentication | 15 minutes | login, token refresh, and logout succeed | 10 seconds |
| Billing webhook | 30 minutes | signed test event is accepted once and replay is idempotent | 10 seconds |

Alert after two consecutive failures, except health and authentication which alert immediately when the critical threshold is met. Tag all traffic `synthetic=true` and exclude it from product analytics, not availability telemetry.
