"""Machine-readable platform dependency graph and failure-impact analysis."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DependencyDefinition:
    """Describe one platform component and the dependencies it requires."""

    name: str
    kind: str
    dependencies: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()
    version: str = "unspecified"
    owner: str = "platform"
    degradation: str = "unavailable"

    def __post_init__(self) -> None:
        """Reject malformed definitions before they enter the graph."""
        if not self.name.strip() or not self.kind.strip():
            raise ValueError("dependency name and kind are required")
        if set(self.dependencies) & set(self.optional_dependencies):
            raise ValueError("a dependency cannot be both required and optional")


class DependencyRegistry:
    """Own the validated platform graph without starting or stopping services.

    The registry is an architecture and observability boundary, not a service
    locator. Callers register definitions, validate the complete graph, read
    deterministic startup/shutdown ordering, and calculate the blast radius of
    an unavailable component. It performs no network, database, or process
    lifecycle side effects.
    """

    def __init__(self, definitions: tuple[DependencyDefinition, ...] = ()) -> None:
        self._definitions: dict[str, DependencyDefinition] = {}
        for definition in definitions:
            if definition.name in self._definitions:
                raise ValueError(f"dependency already registered: {definition.name}")
            self._definitions[definition.name] = definition
        self.validate()

    def register(self, definition: DependencyDefinition) -> None:
        """Add or replace a component, rejecting duplicate names and cycles."""
        if definition.name in self._definitions:
            raise ValueError(f"dependency already registered: {definition.name}")
        unknown = set(definition.dependencies) | set(definition.optional_dependencies)
        unknown -= set(self._definitions) | {definition.name}
        if unknown:
            raise ValueError(f"unknown dependencies: {', '.join(sorted(unknown))}")
        self._definitions[definition.name] = definition
        try:
            self.validate()
        except Exception:
            del self._definitions[definition.name]
            raise

    def validate(self) -> None:
        """Validate references and reject every required or optional cycle."""
        names = set(self._definitions)
        for definition in self._definitions.values():
            references = set(definition.dependencies) | set(definition.optional_dependencies)
            missing = references - names
            if missing:
                raise ValueError(f"unknown dependencies: {', '.join(sorted(missing))}")
        self._topological_order()

    def startup_order(self) -> tuple[str, ...]:
        """Return dependencies before dependants in deterministic order."""
        return self._topological_order()

    def shutdown_order(self) -> tuple[str, ...]:
        """Return the safe reverse of startup order."""
        return tuple(reversed(self._topological_order()))

    def impact_analysis(self, unavailable: set[str] | frozenset[str]) -> dict[str, Any]:
        """Calculate blocked and degraded components for unavailable services.

        Required dependencies transitively block a component. Optional
        dependencies only degrade the component, while their own downstream
        impact is still evaluated independently.
        """
        unavailable_set = {str(item) for item in unavailable}
        unknown = unavailable_set - set(self._definitions)
        if unknown:
            raise ValueError(f"unknown unavailable components: {', '.join(sorted(unknown))}")
        blocked = set(unavailable_set)
        degraded: set[str] = set()
        changed = True
        while changed:
            changed = False
            for name, definition in self._definitions.items():
                if name in blocked:
                    continue
                if any(dep in blocked for dep in definition.dependencies):
                    blocked.add(name)
                    changed = True
                elif any(dep in blocked or dep in degraded for dep in definition.optional_dependencies):
                    if name not in degraded:
                        degraded.add(name)
                        changed = True
        return {
            "unavailable": tuple(sorted(unavailable_set)),
            "blocked": tuple(sorted(blocked - unavailable_set)),
            "degraded": tuple(sorted(degraded - blocked)),
            "healthy": tuple(sorted(set(self._definitions) - blocked - degraded)),
        }

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe graph projection for operations tooling."""
        return {
            "components": {
                name: {
                    "kind": item.kind,
                    "dependencies": list(item.dependencies),
                    "optional_dependencies": list(item.optional_dependencies),
                    "version": item.version,
                    "owner": item.owner,
                    "degradation": item.degradation,
                }
                for name, item in sorted(self._definitions.items())
            },
            "startup_order": list(self.startup_order()),
            "shutdown_order": list(self.shutdown_order()),
        }

    def _topological_order(self) -> tuple[str, ...]:
        """Sort the graph or raise a cycle error with stable diagnostics."""
        edges: dict[str, set[str]] = defaultdict(set)
        indegree = {name: 0 for name in self._definitions}
        for name, definition in self._definitions.items():
            for dependency in (*definition.dependencies, *definition.optional_dependencies):
                edges[dependency].add(name)
                indegree[name] += 1
        ready = deque(sorted(name for name, degree in indegree.items() if degree == 0))
        ordered: list[str] = []
        while ready:
            name = ready.popleft()
            ordered.append(name)
            for child in sorted(edges[name]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        if len(ordered) != len(indegree):
            cycle = sorted(name for name, degree in indegree.items() if degree > 0)
            raise ValueError(f"dependency cycle detected: {', '.join(cycle)}")
        return tuple(ordered)


DEFAULT_DEPENDENCIES = (
    DependencyDefinition("configuration", "platform", version="ISSUE_045", owner="platform"),
    DependencyDefinition("authentication", "security", ("configuration",), version="ISSUE_066", owner="security"),
    DependencyDefinition("database", "persistence", ("configuration",), version="postgresql", owner="data"),
    DependencyDefinition("redis", "infrastructure", ("configuration",), version="redis", owner="platform"),
    DependencyDefinition("market-data", "provider", ("configuration",), version="provider-gateway", owner="data"),
    DependencyDefinition("capabilities", "authorization", ("configuration",), version="ISSUE_046", owner="security"),
    DependencyDefinition("cache", "infrastructure", ("redis",), optional_dependencies=(), version="ISSUE_041", owner="platform"),
    DependencyDefinition("analysis-engine", "domain", ("database", "market-data"), version="current", owner="research"),
    DependencyDefinition("analysis-worker", "worker", ("analysis-engine", "redis"), version="ISSUE_047", owner="research"),
    DependencyDefinition("web", "application", ("authentication", "database", "capabilities"), optional_dependencies=("cache",), version="current", owner="product"),
    DependencyDefinition("operations-dashboard", "operations", ("web",), optional_dependencies=("analysis-worker", "market-data", "cache"), version="ISSUE_053", owner="platform"),
)

dependency_registry = DependencyRegistry(DEFAULT_DEPENDENCIES)
