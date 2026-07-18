"""Authorized, audited, low-risk actions for the internal operations console."""

from __future__ import annotations

from typing import Any, Mapping

from codes.core.config import configuration_service
from codes.services import component_cache, feature_management, provider_gateway
from codes.services.audit_journal import audit_journal

CONFIRMATION_PREFIX = "confirm:"
AVAILABLE_ACTIONS = (
    "feature.kill_switch",
    "configuration.reload",
    "configuration.rollback",
    "provider.reset_circuit",
    "cache.clear_local",
)


def describe() -> dict[str, Any]:
    """Return the safe action catalogue and explicitly excluded action classes."""
    return {
        "available_actions": list(AVAILABLE_ACTIONS),
        "confirmation": "Send confirmation equal to `confirm:<action>`.",
        "excluded": [
            "database mutations",
            "user-data operations",
            "queue/job deletion or release",
            "process restart and shell access",
        ],
    }


def execute(
    action: str,
    *,
    actor: str,
    confirmation: str,
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one allowlisted reversible action after exact confirmation.

    The caller must already have authenticated and authorized ``actor``. This
    service validates the action and parameters, invokes only project-owned
    administrative boundaries, and records a redacted audit event. It never
    accepts SQL, shell commands, arbitrary feature definitions, or credentials.
    """
    normalized = str(action or "").strip().lower()
    if normalized not in AVAILABLE_ACTIONS:
        raise ValueError("action is not allowlisted")
    if confirmation != f"{CONFIRMATION_PREFIX}{normalized}":
        raise ValueError("exact action confirmation is required")
    values = dict(parameters or {})
    if not actor:
        raise ValueError("actor is required")
    handlers = {
        "feature.kill_switch": _feature_kill_switch,
        "configuration.reload": _configuration_reload,
        "configuration.rollback": _configuration_rollback,
        "provider.reset_circuit": _provider_reset,
        "cache.clear_local": _clear_local_cache,
    }
    result = handlers[normalized](actor, values)
    audit_journal.record(
        "operations_action",
        action=normalized,
        actor_id=actor,
        component="operations_console",
        details=result,
    )
    return result


def _feature_kill_switch(actor: str, values: Mapping[str, Any]) -> dict[str, Any]:
    """Apply one typed feature kill-switch change."""
    feature = str(values.get("feature") or "").strip()
    if not feature:
        raise ValueError("feature is required")
    enabled = _strict_bool(values.get("enabled"))
    feature_management.set_kill_switch(feature, enabled, actor=actor)
    return {"feature": feature, "kill_switch": enabled}


def _configuration_reload(actor: str, _values: Mapping[str, Any]) -> dict[str, Any]:
    """Reload configuration through the validated runtime service."""
    change = configuration_service().reload(actor=actor)
    return {"version": change.version, "changed": list(change.changed)}


def _configuration_rollback(actor: str, values: Mapping[str, Any]) -> dict[str, Any]:
    """Rollback to a prior validated configuration snapshot."""
    version = values.get("version")
    if version is not None:
        try:
            version = int(version)
        except (TypeError, ValueError) as exc:
            raise ValueError("version must be an integer") from exc
    snapshot = configuration_service().rollback(version=version, actor=actor)
    return {"version": snapshot.version, "pending_restart": list(snapshot.pending_restart)}


def _provider_reset(_actor: str, values: Mapping[str, Any]) -> dict[str, Any]:
    """Reset one registered provider circuit without provider I/O."""
    provider = str(values.get("provider") or "").strip().lower()
    if not provider:
        raise ValueError("provider is required")
    if not provider_gateway.reset_circuit(provider):
        raise ValueError("provider circuit is not registered")
    return {"provider": provider, "reset": True}


def _clear_local_cache(_actor: str, _values: Mapping[str, Any]) -> dict[str, Any]:
    """Clear only the local component cache."""
    component_cache.clear_local()
    return {"local_entries_cleared": True}


def _strict_bool(value: Any) -> bool:
    """Accept only actual booleans to prevent ambiguous action requests."""
    if not isinstance(value, bool):
        raise ValueError("enabled must be a boolean")
    return value
