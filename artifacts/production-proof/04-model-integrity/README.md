# Phase 4 Model Integrity Evidence

**Status:** Lifecycle and regression controls implemented; independent calculation approval remains open.  
**Evidence date:** 2026-07-14

## Implemented

- Machine-readable manifest for all 20 production models with version, section, disclosure level, cost, cacheability, and existing-stock backfill contract.
- Release test fails when the checked-in manifest differs from executable registry metadata.
- Full suite covers missing/null/extreme financial inputs, model-specific calculations, factor extraction, persisted snapshots, UI registration, and backfill queue behavior.
- Analysis payload records the complete model-version map and analysis version.
- Historical factor snapshots support point-in-time lookup; remaining backtest bias is explicitly surfaced.

## Open Certification Evidence

- [ ] Independently calculated golden workbook/dataset approved for every production model.
- [ ] Golden companies cover financial institutions, negative equity, missing/restated filings, splits, foreign issuers, and malformed inputs.
- [ ] Source document, filing, unit/currency, retrieval, normalization, and model versions are traceable in every persisted result.
- [ ] Differential report and approved tolerance accompany every model-version change.
- [ ] Independent quantitative reviewer signs model calculations and bias disclosures.
