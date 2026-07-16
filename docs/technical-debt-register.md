# Prioritized Architecture Technical-Debt Register

Status values are `planned`, `partial`, `migrated`, or `accepted-low-risk`.
Items are not architecture exceptions: new coupling remains prohibited.

| ID | Severity | Scope | Evidence / risk | Owner | Dependencies | Status | Removal trigger |
|---|---|---|---|---|---|---|---|
| TD-077-01 | Critical | `codes/services/stock_analysis.py` | 594 lines; `_analyze_stock` complexity 75; provider/cache/persistence/job orchestration | Analysis platform | Golden suite, repository ports | Partial | Extract primary inputs, result persistence, and secondary enrichment use cases without output changes |
| TD-077-02 | Critical | `codes/data/db.py` | 2,020 lines; unrelated schemas and implicit transaction boundaries | Data platform | Issue 059–064 direction | Planned | Consumers use narrow repositories and transaction owners; compatibility facade removed |
| TD-077-03 | Critical | Buffett/Graham/Piotroski/scorer | Financially sensitive functions complexity 117/78/73/47 | Quant models | Golden datasets and explicit formula review | Planned | Cohesive calculation stages are independently tested with identical golden output |
| TD-077-04 | High | `api_fetcher.py`, `sec_data.py` | 1,086/1,165 lines; HTTP, retry, cache, normalization combined | Market data | Provider ports and contract tests | Partial | Each provider client returns canonical payloads through focused adapters |
| TD-077-05 | High | `analysis_ui.py` | 1,674 lines; content builder 435 lines; duplicate `_fmt` helpers | Frontend | Issue 075 | Planned | Design-engine financial components/view models replace duplicate format/render logic |
| TD-077-06 | High | Screener tab/engine | 870/551 lines; high change frequency; render callback complexity 62 | Screener | Issue 075, repository split | Planned | Query/use case/view model/rendering independently tested |
| TD-077-07 | High | Portfolio tab/domain | 819/966 lines; persistence, simulation, rendering coupled across callers | Portfolio | Repository split, Issue 075 | Planned | Portfolio repository and use cases precede typed view models/components |
| TD-077-08 | Medium | Whole-tree typing/lint | 1,076 strict mypy and 182 Ruff baseline findings | Code owners by package | Incremental protected set | Partial | Each touched module enters strict mypy/Ruff gate; baseline reaches zero |
| TD-077-09 | Medium | Mutable globals/config reads | 68 mutable module globals; 100 environment reads | Platform | Issue 045 configuration service | Planned | Volatile state/config is injected in concurrency-sensitive/test-sensitive paths |
| TD-077-10 | Medium | Duplicate helpers/flag APIs | 8 exact duplicate groups; 23 boolean-default functions | Code owners by package | Reference contract tests | Planned | Duplicate behavior has one owner; ambiguous booleans become explicit policy/value objects when changed |
| TD-077-11 | Low | Large SCSS partials | `company_analysis.scss` 796 lines; `_company.scss` 535; `_screener.scss` 519 | Frontend | Issue 075 | Accepted-low-risk | Migrate by component when design-engine primitives land; no cosmetic split |

## Completed register entries

| ID | Scope | Result |
|---|---|---|
| ARCH-001 | Presentation-owned stock analysis | Migrated to `codes.services.stock_analysis`; allowlist removed |
| ARCH-002 | HTTP in universe engine | Migrated to `SecTickerUniverseAdapter`; HTTP allowlist removed |
| ARCH-003 | Flask in product analytics service | Migrated to injected `AnalyticsContext`; service-framework gate added |
