"""Acceptance tests for the ISSUE_054 platform dependency graph."""

import pytest

from codes.services.dependency_registry import DependencyDefinition, DependencyRegistry


def test_registry_rejects_cycles_and_exposes_ordering() -> None:
    registry = DependencyRegistry()
    registry.register(DependencyDefinition("base", "service"))
    registry.register(DependencyDefinition("worker", "service", ("base",)))

    assert registry.startup_order() == ("base", "worker")
    assert registry.shutdown_order() == ("worker", "base")
    with pytest.raises(ValueError, match="unknown dependencies"):
        registry.register(DependencyDefinition("bad", "service", ("missing",)))


def test_registry_rejects_cycle_when_definition_is_injected() -> None:
    with pytest.raises(ValueError, match="dependency cycle"):
        DependencyRegistry(
            (
                DependencyDefinition("a", "service", ("b",)),
                DependencyDefinition("b", "service", ("a",)),
            )
        )


def test_optional_failure_degrades_only_dependants_and_required_failure_blocks() -> None:
    registry = DependencyRegistry(
        (
            DependencyDefinition("base", "service"),
            DependencyDefinition("optional", "service", ("base",)),
            DependencyDefinition("app", "service", ("base",), ("optional",)),
            DependencyDefinition("unrelated", "service", ("base",)),
        )
    )

    impact = registry.impact_analysis({"optional"})
    assert impact["degraded"] == ("app",)
    assert impact["blocked"] == ()
    assert impact["healthy"] == ("base", "unrelated")

    impact = registry.impact_analysis({"base"})
    assert set(impact["blocked"]) == {"app", "optional", "unrelated"}


def test_default_registry_is_visible_in_operations_snapshot(monkeypatch) -> None:
    from codes.services import operations_dashboard

    monkeypatch.setattr(operations_dashboard, "_health", lambda: {"state": "NORMAL"})
    monkeypatch.setattr(operations_dashboard.performance_metrics, "snapshot", lambda: {})
    monkeypatch.setattr(operations_dashboard.provider_gateway, "health", lambda: {})
    monkeypatch.setattr(operations_dashboard.analysis_jobs, "health", lambda: {})
    monkeypatch.setattr(operations_dashboard.component_cache, "stats", lambda: {})
    monkeypatch.setattr(operations_dashboard.db, "pool_health", lambda: {})
    monkeypatch.setattr(operations_dashboard.analytics_db, "pool_health", lambda: {})
    monkeypatch.setattr(operations_dashboard.audit_journal, "search", lambda **_: ())

    snapshot = operations_dashboard.snapshot()
    assert "analysis-engine" in snapshot["dependency_graph"]["components"]
