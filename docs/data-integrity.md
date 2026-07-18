# Financial data integrity (ISSUE_050)

`codes.services.data_integrity.FinancialDataIntegrityEngine` is the trust
boundary after provider normalization and before persistence or scoring. It
checks required identity fields, record shapes, finite numeric values, annual
period bounds, duplicate periods, positive shares, and balance-sheet
reconciliation. A failed payload is rejected, recorded as redacted quarantine
metadata, and cannot replace an accepted value in the engine's last-known-valid
store.

Provider adapters remain responsible for provider-specific parsing, units,
currency, filing provenance, and normalization. The integrity engine does not
invent missing values or turn warnings into zeros. Rejected records are
audited by provider, symbol, quality score, and issue codes; raw payloads and
credentials are not written to logs.

The current quarantine and last-known-valid index is process-local. Durable
quarantine retention and cross-worker last-known-valid reads must be provided
by the owning ingestion database before multi-worker production rollout.
