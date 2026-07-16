# Adaptive loading and async UX

This contract keeps feedback proportional to the operation and preserves useful
content while independent work continues. Timing thresholds are centralized in
`codes.services.adaptive_loading.LoadingPolicy`; components are centralized in
`codes.app_modules.design_system.states`.

| Operation | Expected | Pattern | Scope | Measurable | Resumable |
|---|---:|---|---|---|---|
| Tab switch | <250 ms | Immediate control feedback | Trigger | No | No |
| Cached analysis | 250–1,000 ms | Delayed loader | Analysis section | No | No |
| Quote or chart refresh | 1–3 s | Reserved skeleton | Card/chart | No | No |
| Fresh analysis | 3–10 s | Named staged progress | Independent sections | Yes | No |
| Screener refresh | 3–10 s | Named staged progress | Rows; controls remain usable | Yes | No |
| Portfolio simulation | >10 s | Background job | Simulation results | Yes | Yes |
| Factor backtest | >10 s | Background job | Backtest results | Yes | Yes |
| Authentication/billing | 1–3 s | Scoped loader | Shell/form | No | No |

Loaders wait 250 ms before appearing and remain visible for at least 200 ms to
avoid flashes. Existing results stay visible during refresh. Charts reserve
their dimensions and report failures locally with local retry actions. Empty,
partial, stale, unavailable, and error states use different copy and semantics.

Long simulations and backtests use stable job IDs derived from the owner and
inputs. Status is persisted for 24 hours, the browser stores the current job ID,
and polling reconnects after navigation. Jobs expose honest named stages and
completed work units; they never invent percentages. Cancellation is cooperative.
Retries are bounded exponential backoff with jitter, and validation, permission,
entitlement, and not-found failures are never retried.

The `/_internal/performance` snapshot includes privacy-safe
UI operation latency, first-useful-result latency, outcomes, retry counts, stale
fallback counts, and section counts. It never records symbols, portfolio names,
filter text, or user identifiers.

Accessibility rules: async containers expose `aria-busy`; delayed announcements
use polite live regions; determinate progress uses native progress semantics;
skeleton animation honors reduced motion. Controls, prior results, and local
retry/cancel actions remain keyboard and touch accessible in both themes.
