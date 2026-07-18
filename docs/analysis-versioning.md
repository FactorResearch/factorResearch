# Versioned analysis engine (ISSUE_051)

New analyses carry an immutable `analysis_manifest` containing platform,
analysis, model, normalization, provider-mapping, configuration, market,
source, and filing-period versions. The manifest is persisted with official
snapshots and travels with analysis responses.

Historical snapshots are append-only. Methodology changes must change
`ANALYSIS_VERSION` or a registered model version. Historical comparisons refuse
to calculate deltas when non-legacy manifests disagree on methodology,
normalization, provider mapping, market, or model versions. Legacy snapshots
without a manifest remain readable until regenerated.
