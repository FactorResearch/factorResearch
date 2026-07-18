# Data lineage and freshness (ISSUE_055)

## Contract

Cached and persisted datasets carry a JSON-safe `lineage` object with:

- `source`: provider, database, or explicit user-input boundary;
- `acquired_at`: UTC time Cenvarn obtained the payload;
- `source_timestamp`: provider observation, filing, or quote time when supplied;
- `freshness_policy`: the invalidation rule (`filing-aware` for SEC facts);
- `freshness_state`: `current`, `stale`, `expired`, or `unavailable`.

The metadata is descriptive. Domain validators still decide whether a value is
safe to calculate with, and a missing timestamp is never treated as current.

## Freshness policy

TTL-backed datasets become `stale` after one TTL and `expired` after two TTLs.
Filing-aware datasets are compared with the newest known filing and do not use
an invented wall-clock TTL. Historical analysis snapshots retain their source
lineage and methodology manifest in the immutable `official_metrics` payload.

## Rollout and recovery

The cache envelope change is backward-compatible: legacy entries remain
readable, but their lineage is unavailable until the next write. No database
migration is required because snapshot provenance is stored in the existing
JSONB payload. Rollback is a code rollback; already-written lineage fields are
ignored safely by older readers.
