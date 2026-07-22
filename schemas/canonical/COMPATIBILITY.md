# Canonical schema compatibility

The canonical schema uses semantic versions. Every serialized object and
columnar schema records the exact version that defines its meaning.

- Patch releases may clarify documentation or tighten a constraint only when
  all already-valid values remain valid.
- Minor releases may add optional fields. Enum additions require consumers to
  preserve or reject unknown values explicitly rather than silently mapping
  them to an existing state.
- Major releases cover removals, required-field additions, type changes, unit
  changes, or changes in financial meaning.

Breaking changes require a new side-by-side schema directory, read and write
adapters, migration evidence for persisted data, a compatibility window, and a
documented rollback or forward-recovery plan. Existing version directories are
immutable after consumers ship.

JSON is used for control objects and product APIs. Exact decimals are JSON
strings. Arrow is used for in-process tables and Arrow IPC for cross-process
columnar data. Parquet consumers must embed the same schema and semantic
version metadata. No custom binary format is permitted.
