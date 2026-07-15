# Bad Model or Data Release

1. Identify model/version/provider scope from result provenance and compare golden-set failures.
2. Disable the affected feature flag or cold analysis path; keep known-good snapshots visibly versioned.
3. Do not overwrite prior results until the defect and affected population are known.
4. Roll back code/model or provider mapping, then run golden, invariant, and representative ticker tests.
5. Recompute a bounded affected sample and compare before bulk remediation.
6. Record affected users/results and involve legal/privacy when published decisions were materially wrong.
