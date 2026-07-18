# Platform dependency registry (ISSUE_054)

`codes.services.dependency_registry` is the machine-readable architecture
registry for major platform components. It records component kind, owner,
version, required dependencies, optional dependencies, and the declared
degradation posture.

The registry is observation and validation only. It does not start, stop,
restart, or discover services. Registration rejects missing references and
cycles across both required and optional edges. `startup_order()` and
`shutdown_order()` provide deterministic lifecycle documentation for deploy
and incident tooling.

`impact_analysis()` distinguishes a required dependency outage, which blocks
transitive dependants, from an optional dependency outage, which marks only
the affected dependants degraded. The operations snapshot exposes the graph
under `dependency_graph` so operators can correlate health failures with
customer-impacting workflows.

Adding a component requires an owner, version or compatibility marker, a
failure/degradation strategy, and tests for its dependency edges. This change
has no database migration, external package, or runtime lifecycle side effect.
