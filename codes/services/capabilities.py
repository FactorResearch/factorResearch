"""Configuration-driven capability authorization for user-owned features.

The service is independent of Flask, billing persistence, and endpoint code.
Invalid configuration, unknown capabilities, expired overrides, and missing
dependencies fail closed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "capabilities.json"
DECISION_CACHE_TTL_SECONDS = 1.0


@dataclass(frozen=True)
class CapabilityDecision:
    """Result of a capability evaluation, including safe diagnostic context."""

    allowed: bool
    capability: str
    reason: str = ""
    source: str = "denied"
    config_version: str = ""


@dataclass(frozen=True)
class CapabilityOverride:
    """User-scoped temporary grant or denial with an absolute UTC expiry."""

    enabled: bool
    expires_at: datetime
    actor: str


class CapabilityService:
    """Resolve capability access from reloadable policy configuration."""

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
        self._config_path = config_path
        self._lock = RLock()
        self._config_mtime_ns: int | None = None
        self._config: dict[str, Any] | None = None
        self._generation = 0
        self._overrides: dict[tuple[str, str], CapabilityOverride] = {}
        self._decisions: dict[tuple[Any, ...], tuple[float, CapabilityDecision]] = {}

    def evaluate(
        self,
        user_id: str,
        capability: str,
        *,
        plan: str | None,
        status: str | None,
        now: datetime | None = None,
    ) -> CapabilityDecision:
        """Return whether an authenticated user can use a capability."""
        current = _as_utc(now or datetime.now(timezone.utc))
        normalized = str(capability or "").strip().lower()
        with self._lock:
            config = self._load_config_locked()
            version = str(config.get("version", "")) if config else ""
            override = self._active_override_locked(user_id, normalized, current)
            cache_key = (
                self._generation, user_id, normalized,
                str(plan or "").strip().lower(), str(status or "").strip().lower(),
                override.enabled if override else None,
                override.expires_at if override else None,
            )
            cached = self._decisions.get(cache_key)
            if cached and (current.timestamp() - cached[0]) < DECISION_CACHE_TTL_SECONDS:
                return cached[1]
            decision = self._evaluate_locked(config, user_id, normalized, str(plan or ""), current, set())
            if decision.config_version != version:
                decision = CapabilityDecision(decision.allowed, decision.capability, decision.reason, decision.source, version)
            self._decisions[cache_key] = (current.timestamp(), decision)
            return decision

    def set_override(
        self,
        user_id: str,
        capability: str,
        *,
        enabled: bool,
        expires_at: datetime,
        actor: str,
    ) -> None:
        """Set a validated user-specific override until an absolute UTC time."""
        normalized = str(capability or "").strip().lower()
        expiry = _as_utc(expires_at)
        with self._lock:
            config = self._load_config_locked()
            definitions = config.get("capabilities", {}) if config else {}
            if not user_id or normalized not in definitions:
                raise ValueError("cannot override an unknown capability")
            if expiry <= datetime.now(timezone.utc):
                raise ValueError("capability override must expire in the future")
            if not actor:
                raise ValueError("capability override actor is required")
            self._overrides[(user_id, normalized)] = CapabilityOverride(bool(enabled), expiry, actor)
            self._invalidate_locked()

    def clear_override(self, user_id: str, capability: str) -> None:
        """Remove a user-specific override and invalidate cached decisions."""
        with self._lock:
            self._overrides.pop((user_id, str(capability or "").strip().lower()), None)
            self._invalidate_locked()

    def analysis_limit(self, plan: str | None) -> int | None:
        """Return the configured analysis quota for a subscription plan."""
        with self._lock:
            config = self._load_config_locked()
            plan_data = self._resolved_plan_locked(config, str(plan or "")) if config else None
            limit = plan_data.get("analysis_limit") if plan_data else None
            return int(limit) if isinstance(limit, int) and limit >= 0 else None

    def _evaluate_locked(
        self,
        config: dict[str, Any] | None,
        user_id: str,
        capability: str,
        plan: str,
        now: datetime,
        visiting: set[str],
    ) -> CapabilityDecision:
        version = str(config.get("version", "")) if config else ""
        definitions = config.get("capabilities", {}) if config else {}
        definition = definitions.get(capability) if isinstance(definitions, dict) else None
        if not isinstance(definition, dict):
            return CapabilityDecision(False, capability, "Capability is not registered.", config_version=version)
        if capability in visiting:
            return CapabilityDecision(False, capability, "Capability dependency cycle detected.", config_version=version)
        override = self._active_override_locked(user_id, capability, now)
        if override and not override.enabled:
            return CapabilityDecision(False, capability, "Capability is temporarily disabled.", "override", version)
        allowed = self._plan_grants_locked(config, plan, capability)
        if override and override.enabled:
            allowed = True
        if not allowed:
            return CapabilityDecision(False, capability, str(definition.get("denial_message") or "Capability access denied."), "policy", version)
        dependencies = definition.get("dependencies", [])
        for dependency in dependencies:
            child = self._evaluate_locked(config, user_id, dependency, plan, now, visiting | {capability})
            if not child.allowed:
                return CapabilityDecision(False, capability, f"Required capability unavailable: {dependency}.", child.source, version)
        return CapabilityDecision(True, capability, source="override" if override else "policy", config_version=version)

    def _load_config_locked(self) -> dict[str, Any] | None:
        try:
            mtime = self._config_path.stat().st_mtime_ns
            if self._config is not None and mtime == self._config_mtime_ns:
                return self._config
            config = _validate_config(json.loads(self._config_path.read_text(encoding="utf-8")))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._config = None
            self._config_mtime_ns = None
            self._generation += 1
            self._decisions.clear()
            LOGGER.error("Capability policy unavailable; denying access: %s", exc)
            return None
        self._config = config
        self._config_mtime_ns = mtime
        self._generation += 1
        self._decisions.clear()
        return config

    def _resolved_plan_locked(self, config: dict[str, Any], plan: str) -> dict[str, Any] | None:
        plans = config.get("plans", {})
        current = plans.get(plan.strip().lower()) if isinstance(plans, dict) else None
        seen: set[str] = set()
        while isinstance(current, dict) and isinstance(current.get("inherits"), str):
            name = str(current["inherits"]).strip().lower()
            if name in seen:
                return None
            seen.add(name)
            current = plans.get(name)
        return current if isinstance(current, dict) else None

    def _plan_grants_locked(self, config: dict[str, Any], plan: str, capability: str) -> bool:
        plan_data = self._resolved_plan_locked(config, plan)
        grants = plan_data.get("capabilities", []) if plan_data else []
        return isinstance(grants, list) and capability in grants

    def _active_override_locked(self, user_id: str, capability: str, now: datetime) -> CapabilityOverride | None:
        override = self._overrides.get((user_id, capability))
        if override and override.expires_at > now:
            return override
        if override:
            self._overrides.pop((user_id, capability), None)
        return None

    def _invalidate_locked(self) -> None:
        self._generation += 1
        self._decisions.clear()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _validate_config(raw: Any) -> dict[str, Any]:
    """Validate policy shape and references before it can grant access."""
    if not isinstance(raw, dict) or not isinstance(raw.get("version"), str):
        raise ValueError("capability policy requires a string version")
    plans = raw.get("plans")
    definitions = raw.get("capabilities")
    if not isinstance(plans, dict) or not isinstance(definitions, dict) or not definitions:
        raise ValueError("capability policy requires plans and capabilities")
    names = set(definitions)
    for name, definition in definitions.items():
        if not isinstance(name, str) or not isinstance(definition, dict):
            raise ValueError(f"capability definition is invalid: {name}")
        dependencies = definition.get("dependencies", [])
        if not isinstance(dependencies, list) or any(dep not in names for dep in dependencies):
            raise ValueError(f"capability dependencies are invalid: {name}")
    for name, plan in plans.items():
        if not isinstance(plan, dict):
            raise ValueError(f"plan definition is invalid: {name}")
        grants = plan.get("capabilities", [])
        if "inherits" not in plan and (not isinstance(grants, list) or any(item not in names for item in grants)):
            raise ValueError(f"plan capabilities are invalid: {name}")
    return raw


capability_service = CapabilityService()
