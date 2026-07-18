"""Read-only, failure-isolated data for the internal operations dashboard.

The dashboard is deliberately an aggregation boundary: it observes existing
health and audit sources, redacts nothing further than their owning services,
and never performs recovery or mutates production state. Each optional source
is isolated so an unavailable provider, queue, or database pool cannot take
down the operational view itself.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from codes.data import analytics_db, db
from codes.services import analysis_jobs, component_cache, performance_metrics, provider_gateway
from codes.services.audit_journal import audit_journal
from codes.services.dependency_registry import dependency_registry
from codes.services.operational_controller import classify_runtime_health, controller


def _observe(name: str, callback: Callable[[], Any]) -> dict[str, Any]:
    """Return one bounded observation without allowing source failures to escape."""
    try:
        value = callback()
        return {"status": "available", "value": value}
    except Exception as exc:
        return {
            "status": "unavailable",
            "value": None,
            "error": f"{name} probe failed: {type(exc).__name__}",
        }


def _health() -> dict[str, Any]:
    """Evaluate registered health probes and preserve unavailable reports."""
    controller.register_probe(
        "providers",
        lambda: classify_runtime_health("providers", provider_gateway.health()),
    )
    controller.register_probe(
        "analysis-queue",
        lambda: classify_runtime_health("analysis-queue", analysis_jobs.health()),
    )
    return controller.summary()


def snapshot(*, search: str = "", limit: int = 50) -> dict[str, Any]:
    """Build a safe operational snapshot with optional bounded event search.

    ``search`` matches request, correlation, user, job, ticker, provider, or
    component identifiers. It is passed only as an exact field value; broad
    unbounded journal scans are intentionally not supported.
    """
    normalized_search = str(search or "").strip()[:256]
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    events = audit_journal.search(limit=limit, **_search_filter(normalized_search)) if normalized_search else audit_journal.search(limit=limit)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "health": _health(),
        "performance": _observe("performance", performance_metrics.snapshot),
        "provider_circuits": _observe("providers", provider_gateway.health),
        "queue": _observe("analysis queue", analysis_jobs.health),
        "cache": _observe("component cache", component_cache.stats),
        "database_pools": {
            "application": _observe("application database", db.pool_health),
            "analytics": _observe("analytics database", analytics_db.pool_health),
        },
        "events": list(events),
        "event_search": normalized_search,
        "dependency_graph": dependency_registry.snapshot(),
    }


def _search_filter(value: str) -> dict[str, str]:
    """Map one operator query to known journal fields without fuzzy leakage."""
    fields = ("request_id", "correlation_id", "user_id", "job_id", "ticker", "provider", "component")
    return {field: value for field in fields if field in value.lower()} or {"request_id": value}
