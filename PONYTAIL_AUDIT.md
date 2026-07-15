# Ponytail Over-Engineering Audit

**Audit date:** 2026-07-14
**Branch:** `optimization`
**Scope:** Deletion, stdlib/native replacement, unnecessary abstraction, and same-behavior shrinking only. Correctness, security, performance, and product design are intentionally outside this audit.

## Ranked Findings

1. **delete:** Remove the orphaned options signal engine and its dedicated tests; the production analysis and UI intentionally removed options, and only architecture/legal tests still import it. Replacement: nothing; keep the existing factor-momentum card. Estimated cut: 700-730 lines. [`codes/models/options_signal_engine.py`](codes/models/options_signal_engine.py), [`tests/test_options_signal_engine.py`](tests/test_options_signal_engine.py), [`tests/test_v05_architecture.py`](tests/test_v05_architecture.py), [`tests/test_issue_027_legal_safe_labels.py`](tests/test_issue_027_legal_safe_labels.py).

2. **delete:** Remove unused dependencies `dash_svg`, `alpha_vantage`, `flask-session`, and `bleach`; no application or test imports them, Alpha Vantage access is implemented through `requests`, and Flask uses its built-in session. Replacement: existing code. Estimated cut: 4 direct dependencies plus their transitive install surface. [`requirements.txt`](requirements.txt).

3. **delete:** Remove the tracked compiled standalone CSS files from source control and compile them during build/release; SCSS is already the source of truth and CI already installs Sass. Replacement: one build command producing `company_analysis.css`, `error_pages.css`, `legal_pages.css`, and `waitlist.css`. Estimated cut: about 750 generated lines from version control. [`assets/company_analysis.css`](assets/company_analysis.css), [`assets/error_pages.css`](assets/error_pages.css), [`assets/legal_pages.css`](assets/legal_pages.css), [`assets/waitlist.css`](assets/waitlist.css), [`.github/workflows/pr-tests.yml`](.github/workflows/pr-tests.yml).

4. **delete:** Collapse the market-fear data adapter to `return {"vix": None, "vixeq": None, "spread_history": []}` until an index provider exists; all three helper functions and the pandas import are unreachable because their calls are commented out. Replacement: the existing constant neutral result. Estimated cut: 60-65 lines. [`codes/data/market_data.py`](codes/data/market_data.py).

5. **delete:** Remove the custom `MetaPathFinder` legacy import system after changing the single remaining `from codes.sec_data` test import to `from codes.data.sec_data`. Replacement: normal explicit package imports. Estimated cut: 70-75 lines and one process-global import hook. [`codes/__init__.py`](codes/__init__.py), [`tests/test_div_lookback.py`](tests/test_div_lookback.py).

6. **delete:** Remove the unused daily-analysis worker; no production command, scheduler, script, or test imports `run_daily_standard_analysis`. Replacement: the existing analysis scheduler/backfill queue when scheduled analysis is required. Estimated cut: 26 lines. [`codes/workers/daily_analysis_worker.py`](codes/workers/daily_analysis_worker.py), [`codes/services/analysis_scheduler.py`](codes/services/analysis_scheduler.py).

7. **delete:** Remove the chart worker until a process actually calls it; only its own unit test references it, while charts already load through `chart_service` on explicit expansion. Replacement: current on-demand chart service. Estimated cut: 30-45 lines plus test setup. [`codes/workers/chart_worker.py`](codes/workers/chart_worker.py), [`tests/test_issue_041_chart_caching.py`](tests/test_issue_041_chart_caching.py).

8. **delete:** Remove `security.RateLimiter`; production callbacks use `app_modules.rate_limit` and providers use `api_fetcher.RateLimiter`, leaving this third implementation used only by its own tests. Replacement: test the two real limiters. Estimated cut: 25-35 production lines plus three tests. [`codes/security.py`](codes/security.py), [`tests/test_security.py`](tests/test_security.py).

9. **delete:** Remove the country-named screener compatibility API and static `SCREENER_COUNTRIES`; only two Canada tests call it and all application code uses market-named functions. Replacement: `get_screener_market` and `row_matches_market`. Estimated cut: 20-25 lines. [`codes/app_modules/screener_markets.py`](codes/app_modules/screener_markets.py), [`tests/test_track_b_canada_provider.py`](tests/test_track_b_canada_provider.py).

10. **shrink:** Replace the remaining minified `zz_inline_free.css` with the owned SCSS rules that are actually used, then delete `_inline_free.scss` if its single divider rule is already defined elsewhere. Replacement: one semantic utility partial in the normal Sass entrypoint. Estimated cut: one independently loaded asset and duplicate selectors; line savings are misleading because the file is minified. [`assets/zz_inline_free.css`](assets/zz_inline_free.css), [`assets/style/_inline_free.scss`](assets/style/_inline_free.scss), [`assets/style.scss`](assets/style.scss).

11. **shrink:** Delete local `_safe` and `_clamp` wrappers that only delegate to `model_utils.safe_float` and `model_utils.clamp`; call the shared helpers directly. Replacement: `mu.safe_float` and `mu.clamp`. Estimated cut: 35-50 lines across 16 models. [`codes/core/model_utils.py`](codes/core/model_utils.py), [`codes/models`](codes/models).

12. **shrink:** Remove the hard-coded `APP_VERSION` forced reload block; normal asset query fingerprints and the service-worker cache version already handle updates, while a manual version creates another deploy step and can reload every open client. Replacement: existing asset fingerprints/service-worker lifecycle. Estimated cut: 7 lines and one manual release obligation. [`codes/app.py`](codes/app.py).

13. **shrink:** Move the orientation and hidden-dropdown scripts out of five repeated `index_string.replace('</head>', ...)` calls and register one static asset script. Replacement: one `<script src>` insertion or Dash auto-loaded asset. Estimated Python cut: 35-45 lines; total logic remains roughly equal but becomes one testable browser file. [`codes/app.py`](codes/app.py), [`assets/iiq.js`](assets/iiq.js).

14. **shrink:** Use one shared environment helper for production detection instead of repeating the same `FLASK_ENV == "production"` expression in app, auth, billing, cache, session, security, and analysis. Replacement: one `is_production()` function in core configuration. Estimated cut: 15-25 lines and one source of configuration truth. [`codes/app.py`](codes/app.py), [`codes/auth.py`](codes/auth.py), [`codes/billing.py`](codes/billing.py), [`codes/security.py`](codes/security.py), [`codes/data/cache.py`](codes/data/cache.py), [`codes/app_modules/session.py`](codes/app_modules/session.py), [`codes/app_modules/analysis.py`](codes/app_modules/analysis.py).

15. **yagni:** Replace `MarketProviderRegistration.provider_factory` and one-entry `MARKET_PROVIDERS` tuple with a direct Canada registration until a second provider ships; the factory/registry currently adds indirection around one adapter. Replacement: direct Canada adapter selection behind the existing market flag. Estimated cut: 20-30 lines. Keep the registry if another country branch is actively landing now. [`codes/data/providers/registry.py`](codes/data/providers/registry.py).

16. **shrink:** Replace source-text CSS assertions with DOM/behavior checks or a single Sass ownership test; tests that search exact selectors and formatting preserve obsolete implementation rather than product behavior. Replacement: existing axe/layout tests plus one compiled-selector smoke check. Estimated cut: 40-70 test lines. [`tests/test_analysis_overview_layout.py`](tests/test_analysis_overview_layout.py), [`tests/test_analyze_page_layout.py`](tests/test_analyze_page_layout.py), [`tests/test_light_mode_analysis.py`](tests/test_light_mode_analysis.py).

## Do Not Cut

- Input validation, CSRF, encryption, trusted-host handling, accessibility labels, and production rate-limit fail-closed behavior are explicitly protected by Ponytail's safety boundary.
- Model calculations are not removable merely because they are large; each production model is registered, surfaced, versioned, and backfill-capable.
- PostgreSQL, Redis, provider adapters, and the background queue solve current multi-worker and persistence requirements rather than speculative ones.
- The Canada registry becomes justified as soon as a second market implementation is actively developed; do not churn it immediately before that work.

## Aggressive Functional Reduction

The ranked findings above are low-risk deletions. The following cuts are larger and should be executed only in order, with characterization tests captured before each change. They preserve current output and supported behavior; they do not remove models, screens, security controls, accessibility, or deployment capabilities.

17. **shrink:** Replace the one-function-per-analysis-card implementation with two declarative renderers: a metric card schema and a bespoke-component escape hatch. Most of the 14 card functions repeat heading, score, tone, rows, missing-state, and disclosure markup. Keep custom renderers only for genuinely visual cards such as the factor hexagon and charts. Gate: snapshot the Dash component trees for complete, partial, and missing model results before conversion. Estimated cut: 350-500 production lines. [`codes/app_modules/analysis_ui.py`](codes/app_modules/analysis_ui.py).

18. **shrink:** Make the model registry own model execution metadata, result key, default result, cache input, and whether a model belongs to the primary or deferred pass. `_analyze_stock` currently hand-wires every registered model and repeats default construction, timing, caching, exception fallback, and result assignment. Keep explicit hooks for momentum, regime, and other models with unique dependencies. Gate: golden-test the complete analysis payload and model call counts for cached, uncached, partial-data, and deferred runs. Estimated cut: 180-280 production lines. [`codes/core/model_registry.py`](codes/core/model_registry.py), [`codes/app_modules/analysis.py`](codes/app_modules/analysis.py).

19. **shrink:** Remove the Canada-named database wrappers now that callers can use the market-generic methods directly. Functions such as `get_canada_company_profile`, `get_canada_financial_periods`, `get_canada_statement_facts`, and their provenance/document/share equivalents are forwarding aliases, not a separate capability. Gate: migrate callers first and require the Canada ingestion/provider tests to pass. Estimated cut: 35-60 production and compatibility-test lines. [`codes/data/db.py`](codes/data/db.py), [`codes/data/providers`](codes/data/providers), [`tests/test_track_b_canada_db.py`](tests/test_track_b_canada_db.py).

20. **shrink:** Consolidate snapshot persistence onto the application's existing database connection/configuration primitives. `analysis_snapshot_service` independently discovers URLs, opens connections, initializes schema, maps rows, and implements pagination despite the app already owning those concerns in `db`. Do not merge modules merely for fewer files; delete only duplicated connection, schema, and row-mapping machinery behind a small repository API. Gate: run snapshot ownership, public-history, pagination, PostgreSQL, and startup-without-database tests. Estimated cut: 100-170 production lines. [`codes/services/analysis_snapshot_service.py`](codes/services/analysis_snapshot_service.py), [`codes/data/db.py`](codes/data/db.py).

21. **shrink:** Render portfolio metric rows, comparison cards, and holdings columns from data definitions instead of repeated Dash constructors. Preserve callback IDs and component order as an API. Gate: component-tree snapshots at mobile and desktop breakpoints plus simulation and edit callback tests. Estimated cut: 120-200 production lines. [`codes/app_modules/tabs/portfolio.py`](codes/app_modules/tabs/portfolio.py).

22. **shrink:** Parameterize repeated model test cases and retain one focused contract suite per model. Several 400-700-line model tests repeat object construction, missing-field variants, bounds checks, and score-shape assertions. Use tables for input/output cases; do not reduce branch coverage or remove financial formula examples. Gate: branch coverage must be equal or higher before accepting fewer test lines. Estimated cut: 1,200-1,800 test lines across the six largest model suites. [`tests/test_growth_quality.py`](tests/test_growth_quality.py), [`tests/test_fcf_quality.py`](tests/test_fcf_quality.py), [`tests/test_earnings_revision.py`](tests/test_earnings_revision.py), [`tests/test_capital_allocation.py`](tests/test_capital_allocation.py), [`tests/test_profitability.py`](tests/test_profitability.py), [`tests/test_insider_activity.py`](tests/test_insider_activity.py).

23. **shrink:** Replace repeated provider method declarations with one typed provider protocol and a shared neutral implementation for optional capabilities. Current providers repeat statement, filing, profile, shares, provenance, and source-document surfaces. The protocol must remain explicit enough for static checking; avoid dynamic `getattr` dispatch. Gate: provider contract tests must execute unchanged against US and Canada adapters. Estimated cut: 80-140 production lines. [`codes/data/providers`](codes/data/providers), [`codes/data/sec_data.py`](codes/data/sec_data.py).

24. **delete:** Remove migration fallbacks after proving production data no longer contains legacy portfolio cache keys. The `_legacy_*` key family and read-through migration branches permanently double storage behavior for a one-time transition. Gate: add an operational counter, observe zero legacy reads for one full cache-retention window, run a one-time migration, then delete. Estimated cut: 45-80 production and test lines. [`codes/portfolio.py`](codes/portfolio.py).

25. **shrink:** Replace repeated formatting helpers (`_fmt`, `_first`, `_values`, score bounds, missing labels) only where semantics are identical. Name shared helpers by behavior, not convenience, and leave financially distinct normalization local. Gate: mutation/edge-case tests for `None`, NaN, infinity, zero, negative values, and strings. Estimated cut: 80-130 production lines after excluding false duplicates. [`codes/models`](codes/models), [`codes/core/model_utils.py`](codes/core/model_utils.py), [`codes/app_modules/analysis_ui.py`](codes/app_modules/analysis_ui.py).

## Execution Order

1. Apply findings 1-14 and 16; run the full unit, Sass, accessibility, and browser smoke suites.
2. Capture payload/component characterization fixtures, then apply 17, 18, 21, and 22 independently. Revert an individual cut if it needs more branches or indirection than it removes.
3. Apply 19, 20, 23, and 25 after provider and persistence contract coverage is in place.
4. Apply 24 only after production telemetry proves the compatibility path is unused.
5. Re-run dead-code and dependency scans after every phase; aggressive consolidation will expose more deletions that are not safely visible today.

## Rejection Rules

- Do not replace explicit code with reflection, metaprogramming, dynamic imports, or a generic framework merely to lower line count.
- Do not combine unrelated modules if the result has the same total logic and more coupling.
- Do not delete tests unless equivalent behavior and branch coverage remain visible in a smaller parameterized form.
- Do not treat generated files, comments, type hints, validation, telemetry, or accessibility metadata as equivalent kinds of code debt.
- A change fails the Ponytail test if it reduces lines but increases concepts, runtime branches, hidden coupling, or debugging distance.

## Net

Immediate low-risk reduction available: **approximately 1,900-2,100 tracked lines**, **4 direct Python dependencies**, **1 generated browser asset request**, **1 process-global import hook**, and **2 test-only production modules**.

With the aggressive characterization-gated phase, the credible total becomes **approximately 4,200-5,400 tracked lines** without removing current product capability. Roughly half of the additional reduction is repetitive tests; the expected production-code reduction is **1,000-1,500 lines beyond the immediate cuts**. These are targets, not quotas: reject any refactor whose net implementation becomes harder to trace.
