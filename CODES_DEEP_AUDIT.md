# Production Code Deep Audit

**Date:** 2026-07-14  
**Branch:** `optimization`  
**Scope:** `codes/` only. CSS and test line-count reduction are excluded. Tests are verification gates, not optimization targets.

## Rules

- Reduce executed work and concepts before reducing formatting or line count.
- Do not replace explicit financial logic with reflection, metaprogramming, or dynamic dispatch.
- Preserve result schemas, component IDs, security behavior, accessibility, market extensibility, and stored-data compatibility.
- Implement one batch at a time. Compile all of `codes/`, run focused tests, then run the full suite before continuing.
- Reject a refactor if it adds more branches, indirection, or debugging distance than it removes.

## Proposed Batches

### 1. Targeted Bulk Analysis Reads

**Priority:** Highest  
**Risk:** Low  
**Files:** `codes/data/db.py`, `codes/app_modules/tabs/portfolio.py`

Portfolio rendering still calls `db.get_analysis()` once per holding. Add `get_analysis_entries(symbols)` using one `WHERE ticker = ANY(...)` query and use it in the portfolio tab. Keep `list_analysis_entries()` for engines that intentionally load the complete analyzed universe.

**Benefit:** Reduce portfolio database round trips from `N` to `1`; eliminate repeated connection setup and JSON parsing overhead during each render.  
**Gate:** Empty portfolio, missing analyses, malformed JSON, mixed-case symbols, portfolio rendering, full suite.

### 2. Persisted Analysis Row Decoder

**Priority:** High  
**Risk:** Low  
**Files:** `codes/data/db.py`

`get_analysis_entry()` and `list_analysis_entries()` duplicate JSON decoding and malformed-row handling. Introduce one private `_analysis_entry_from_row()` and use it for single, targeted-bulk, and all-analysis reads.

**Benefit:** One compatibility/error policy for persisted analysis payloads and less repeated code.  
**Gate:** Valid JSON, malformed JSON, null payload, timestamp preservation, full DB suite.

### 3. Analysis Pipeline Stage Helpers

**Priority:** High  
**Risk:** Medium  
**Files:** `codes/app_modules/analysis.py`

`_analyze_stock()` is 354 lines and mixes retrieval, core models, optional models, enrichment, result assembly, and persistence. Extract only coherent stages:

1. `_load_primary_inputs(symbol)` for facts, quote, stock history, and benchmark history.
2. `_run_quality_models(...)` for profitability, FCF quality, capital allocation, and growth quality using the existing `_component()` cache boundary.
3. `_persist_analysis_result(...)` for DB write, snapshot, memory cache, and metrics.

Do **not** create a dynamic model framework or loop over arbitrary callables. Models with unique dependencies remain explicit.

**Benefit:** Shorter failure domains, consistent component caching/timing, easier profiling, and removal of repeated persistence/error blocks. Expected reduction: 60-100 production lines.  
**Gate:** Cached, uncached, forced refresh, missing SEC facts, rate-limit error, deferred enrichment, snapshot failure, result golden payload, full suite.

### 4. Optional Model Execution Consistency

**Priority:** Medium  
**Risk:** Medium  
**Files:** `codes/app_modules/analysis.py`, `codes/core/model_registry.py`

Several optional models repeat `result = None`, `try`, calculation, and logging, but not all use `_component()`. Add one explicit `_optional_component()` helper that accepts a stable component name and callback, records the same timing/cache metadata, logs one standardized failure, and returns `None`. Apply only to models whose failure semantics are currently identical.

**Benefit:** Consistent caching and diagnostics with approximately 35-60 fewer lines.  
**Gate:** Per-model exception isolation, cache keys/versions, unchanged output keys, full model and analysis suites.

### 5. Analyze Route Fallback Consolidation

**Priority:** Medium  
**Risk:** Low  
**Files:** `codes/routes/analyze.py`

Company, custom, and historical routes repeat the same Dash-shell fallback branches for missing or invalid snapshots. Introduce one private response helper that converts a missing lookup into the existing shell response without changing status codes, canonical URLs, structured data, or ownership checks.

**Benefit:** Remove repeated control flow and make route failure behavior consistent. Expected reduction: 20-35 lines.  
**Gate:** Company page, custom ownership, historical dates, missing snapshot, canonical URL, structured-data tests.

### 6. Portfolio Simulation Rendering Split

**Priority:** Medium  
**Risk:** Medium  
**Files:** `codes/app_modules/tabs/portfolio.py`

`run_simulation()` and `_build_sim_charts()` contain repeated stats, holdings, weak-link, and Plotly assembly also present in comparison rendering. Reuse existing `_comparison_stats_row()`, `_comparison_holdings_table()`, and `_comparison_weak_link_card()` where component output is equivalent. Keep single and comparison chart builders separate when trace semantics differ.

**Benefit:** One renderer for equivalent portfolio result structures and fewer visual inconsistencies. Expected reduction: 100-160 lines.  
**Gate:** Single simulation, comparison, insufficient holdings, split-adjusted shares, weak links, chart dimensions, mobile component structure.

### 7. Provider and Thread-Pool Ownership

**Priority:** Medium  
**Risk:** Medium  
**Files:** `codes/services/provider_gateway.py`, `codes/app_modules/analysis.py`, `codes/services/analysis_jobs.py`, `codes/services/product_analytics.py`

The process owns four independent executor groups. Document and enforce ownership: provider concurrency belongs to analysis orchestration; gateway owns singleflight/circuit-breaking but should not retain an unused executor. Local jobs and analytics retain bounded dedicated executors. Add shutdown hooks only if deployment tests show workers survive graceful termination.

**Benefit:** Fewer idle threads and clearer concurrency limits.  
**Gate:** Provider concurrency, singleflight, local job fallback, analytics non-blocking behavior, Gunicorn startup/shutdown smoke test.

### 8. Legacy Portfolio Cache Removal With Evidence

**Priority:** Deferred  
**Risk:** High without production evidence  
**Files:** `codes/portfolio.py`

Legacy index, portfolio, and simulation keys still double cache reads and invalidation. Do not delete blindly. First add a counter for successful legacy reads. After one full cache-retention window reports zero reads, migrate remaining keys and remove `_legacy_*` functions and fallback branches.

**Benefit after evidence:** Remove 45-80 lines and up to one failed cache read per portfolio operation.  
**Gate:** Production telemetry, migration dry run, encrypted portfolio cache tests, simulation cache tests.

## Explicit Non-Changes

- Do not split `db.py` merely to create smaller files; that changes file organization without reducing behavior.
- Do not convert financial models to JavaScript. They rely on trusted server data, Python numerical libraries, shared caching, and persisted snapshots; client execution would duplicate logic and expose larger payloads.
- Do not move authentication, billing, provider access, portfolio simulation, or SEC normalization to the browser.
- Do not remove Alpha Vantage raw-request fallback while it remains a configured last-resort provider.
- Do not remove public worker/CLI functions based only on static call counts; deployment systems may invoke them externally.
- Do not remove market registry abstraction while additional country branches are planned.
- Do not delete legacy portfolio keys until telemetry proves they are unused.

## Recommended Order

1. Batch 1 and 2 together: targeted bulk reads plus one decoder.
2. Batch 3: pipeline stages.
3. Batch 4: optional model consistency.
4. Batch 5: route fallback consolidation.
5. Batch 6: portfolio rendering reuse.
6. Batch 7: executor ownership and process smoke tests.
7. Batch 8 only after production evidence.

## Expected Outcome

The immediate batches should remove approximately **220-355 production lines** while reducing database round trips, deferred-analysis latency, duplicated rendering, and orchestration complexity. Batch 8 provides a later **45-80 line** reduction after telemetry. Performance gains will be most visible on portfolios, uncached/deferred analyses, and multi-worker database deployments rather than on a local server and browser running on the same machine.

## Implementation Status

- **Batches 1-2 complete:** targeted portfolio bulk reads and shared persisted-row decoding.
- **Batch 3 partially complete:** persistence is isolated; primary input extraction was rejected because it added error plumbing and branches without reducing logic.
- **Batch 4 complete:** four optional quality models now share versioned caching, timing, and failure handling.
- **Batch 5 complete:** equivalent terminal route fallbacks share one helper.
- **Batch 6 complete:** single and comparison simulations share stats, holdings, and weak-link renderers; distinct charts remain explicit.
- **Batch 7 rejected:** all executor groups are active and isolate different workloads; the provider executor enforces hard timeouts.
- **Batch 8 deferred:** legacy cache removal requires production telemetry across one retention window.

## Fixpoint Audit: 2026-07-14

This follow-up audited all 110 Python files and 28,623 lines under `codes/` in repeated passes. A pass was considered complete only after checking call references, mutable process state, database/network boundaries, concurrency ownership, cache eviction, repeated implementations, request-path initialization, and compile validity. The audit converged after four passes: the final pass found no new issue category or additional high-confidence defect. `python -m compileall -q codes` and `git diff --check` passed. No production files were changed during this audit.

### Critical: Provider Limits Are Released Before Timed-Out Work Stops

**Files:** `codes/services/provider_gateway.py`, `codes/core/singleflight.py`

`provider_gateway.call()` acquires a provider semaphore, submits the callback, and releases the semaphore when `Future.result()` times out. Python cannot stop the running callback, so the request can continue after its permit has been returned. Repeated slow calls can exceed the configured provider concurrency, consume all 16 gateway workers, and make timeouts progressively less effective. Circuit state is also mutated outside `_guard`, allowing concurrent failure increments/resets to overwrite each other.

**Action:** Make the executor own the semaphore for the callback's full lifetime, bound queued work, synchronize circuit transitions, and test that timed-out callbacks cannot exceed the provider limit. Preserve the hard timeout at the caller boundary.

### Critical: Historical Backtests Produce Query/Connection Explosions

**Files:** `codes/engine/backtest.py`, `codes/engine/factor_snapshot.py`, `codes/data/db.py`

For every rebalance date and symbol, `has_sufficient_history()` opens a connection and queries dates; then `get_factor_scores_asof()` opens another connection for every factor. Complexity is approximately `symbols x rebalance_dates x (1 + factors)` database connections and queries. A modest 100-stock, 60-period run can issue tens of thousands of queries before price calculations begin.

**Action:** Add one bulk point-in-time snapshot query for all candidate symbols, factors, and the requested date range. Build an in-memory as-of index once per backtest and make qualification pure Python. Add query-count and result-equivalence tests.

### High: Database Helpers Do Not Use the Pool They Advertise

**Files:** `codes/data/db.py`, `codes/data/analytics_db.py`, `codes/services/analysis_snapshot_service.py`

`db._conn()` says it yields a pooled connection, but `_pg_conn()` calls `psycopg.connect()` for every operation. Analytics events and snapshot storage do the same. This adds connection setup and TLS/authentication overhead to ordinary reads, writes, usage events, and model persistence.

**Action:** Introduce bounded `psycopg_pool.ConnectionPool` instances per DSN with explicit startup/shutdown ownership, health checks, and conservative limits compatible with Gunicorn worker counts. Keep transaction scope at the current context-manager boundaries.

### High: Snapshot Schema Migration Runs on Every Request

**File:** `codes/services/analysis_snapshot_service.py`

Every public snapshot read/write calls `initialize_schema()`, which opens a connection and executes the complete DDL, including `ALTER`, constraint removal, index creation, and a historical `UPDATE`. The function then opens a second connection for the actual operation. This doubles connection traffic and places migration/locking work on hot request paths.

**Action:** Move DDL to deployment migration/startup, retain one thread-safe idempotent readiness check only if startup migration cannot be guaranteed, and never run historical data migration from a read route.

### High: Process Caches Retain Expired Keys Forever

**Files:** `codes/core/singleflight.py`, `codes/services/component_cache.py`, `codes/services/chart_service.py`

Singleflight keeps one lock and one result slot per unique key indefinitely. Component cache entries have expiry timestamps but expired entries are never removed. Chart payloads are correctly capped at 256 entries, but the corresponding lock dictionary is unbounded. Long-lived workers analyzing changing filings/configurations will continually grow these maps.

**Action:** Use bounded LRU/TTL containers, evict expired entries opportunistically, and remove per-key locks only when no waiter can still reference them. Add stress tests over thousands of unique keys and assert stable container sizes.

### High: `score_filtered(top_n=...)` Ignores `top_n`

**File:** `codes/engine/backtest.py`

The strategy accepts, returns, and caches `top_n`, but qualification holds every stock above `min_score`; `top_n` never changes the selected holdings. Users can receive identical results for different advertised portfolio sizes, while the cache stores them as distinct strategies.

**Action:** Rank eligible point-in-time scores and cap each rebalance selection, or remove the parameter from the API/UI if threshold-only behavior is intended. Add a test proving holdings and results change with `top_n`.

### Medium: Importing Data Modules Mutates the Working Directory

**Files:** `codes/data/cache.py`, `codes/data/api_fetcher.py`

Both modules create relative `.cache` directories at import time. Cache location therefore depends on process working directory, imports fail in read-only deployments, and multiple launch methods can silently use different caches.

**Action:** Resolve one configured absolute cache root, create it lazily on first write/lock, and make read-only cache failure non-fatal. Remove duplicate cache-path ownership from `api_fetcher.py`.

### Medium: Confirmed Dead Production Paths and Stale Design Claims

**Files:** `codes/app_modules/tabs/screener.py`, `codes/engine/screener.py`, `codes/data/sec_data.py`, `codes/engine/strategy_cache.py`, `codes/engine/backtest.py`

The following private paths have no runtime or test references: `_quick_peek_takeaway`, `_quick_peek_sections`, `_sec_rate_wait` and its three globals, `_score_one`, `_try_concepts_multins`, `_is_fresh` and `CACHE_TTL_SECONDS`, and `_rebalanced_equal_weight_backtest`. Together they retain roughly 250 lines and stale behavior descriptions. The screener module still documents executor-based scoring that no longer exists.

**Action:** Remove these paths after one focused UI/backtest test run. Update the screener module documentation to describe placeholder loading and persisted-analysis enrichment.

### Medium: Duplicate TTL Assignment Silently Changes Session Behavior

**File:** `codes/engine/screener.py`

`_USER_PROGRESS_TTL` is assigned first to 30 minutes and immediately reassigned to 10 minutes. The second value silently wins, while both comments claim intentional behavior.

**Action:** Keep one configured constant and add a boundary test for stale per-session progress eviction.

### Low: Exact Helpers Are Reimplemented Across Modules

**Files:** `codes/data/db.py`, `codes/data/providers/canada.py`, `codes/models/altman.py`, `codes/models/greenblatt.py`, `codes/models/factor_momentum.py`, `codes/models/growth_quality.py`, `codes/engine/backtest.py`, `codes/engine/factor_backtest.py`

Exact or near-exact implementations remain for `_float_or_none`, `_first`, `_signal`, and `_load_price_history`. Consolidation is worthwhile only where semantics and accepted input types are identical; the broader signal helpers intentionally use model-specific thresholds and should not be forced into a generic abstraction.

**Action:** Move only exact numeric/record/price normalization behavior into existing core helpers, then delete local wrappers. Preserve model-local scoring thresholds.

## Fixpoint Implementation Order

1. Fix provider timeout permit ownership and synchronized circuit state.
2. Bulk-load historical factor snapshots and correct `score_filtered.top_n`.
3. Add real bounded database pools and remove snapshot DDL from requests.
4. Bound all in-process key caches and lock registries.
5. Centralize the cache root and defer directory creation.
6. Delete confirmed dead paths, resolve the duplicate TTL, and consolidate only exact helpers.

Each batch should compile `codes/`, run focused concurrency/query-count/result-equivalence tests, run the complete suite, and pass `git diff --check` before the next batch starts.

## Fixpoint Implementation Status

Implemented on `optimization`:

- Provider permits now remain owned by timed-out callbacks until those callbacks exit; circuit transitions are synchronized.
- Backtests bulk-load factor history once, perform point-in-time lookup in memory, and enforce ranked `score_filtered.top_n` holdings.
- Market, user, analytics, and snapshot stores use bounded, lazy, fork-aware connection pools.
- Snapshot DDL runs only through startup/migration entry points, never from snapshot reads or writes.
- Singleflight results, component results, and chart payloads are bounded; per-key locks use weak registries safe for active waiters.
- Filesystem cache ownership is centralized under `APP_CACHE_DIR` with a stable project default and lazy directory creation.
- Stale screener scoring/rate-limit code, duplicate progress TTL, unused SEC namespace fallback, dead strategy freshness logic, obsolete fixed backtest logic, and the unused quick-peek takeaway were removed.

The large `_quick_peek_sections` renderer remains temporarily because deleting it provides no executed-path performance gain and the quick-peek UI is still under active QA. Near-duplicate model helpers were not consolidated where thresholds or accepted record shapes differ; forcing them together would increase semantic coupling for negligible runtime benefit.

Final verification after the post-review weak-lock correction: `966 passed, 2 skipped`; `python -m compileall -q codes` and `git diff --check` passed.
