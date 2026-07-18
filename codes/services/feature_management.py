"""Central feature evaluation and runtime feature-definition management."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Mapping

from codes.core.redis_client import get_redis

_FEATURE_KEY = "feature-management:definitions"
_DEFAULT_FILE = Path(__file__).resolve().parents[2] / "feature_management.json"
_CACHE_TTL_SECONDS = 1.0


@dataclass(frozen=True)
class FeatureContext:
    """Stable attributes used by feature gates; no secrets are accepted."""

    user_id: str = ""
    subscription: str = ""
    region: str = ""
    internal: bool = False
    beta: bool = False


@dataclass(frozen=True)
class FeatureDecision:
    """Explainable feature result suitable for caller telemetry and UI state."""

    feature: str
    enabled: bool
    reason: str
    definition_version: str | None = None


@dataclass(frozen=True)
class FeatureDefinition:
    """Validated feature policy with safe-disabled defaults."""

    name: str
    owner: str
    purpose: str
    enabled: bool = False
    rollout_percent: int = 0
    subscriptions: frozenset[str] = field(default_factory=frozenset)
    regions: frozenset[str] = field(default_factory=frozenset)
    internal_only: bool = False
    beta_only: bool = False
    dependencies: tuple[str, ...] = ()
    kill_switch: bool = False
    version: str = "1"
    expires_at: str | None = None
    removal_issue: str | None = None


class FeatureDefinitionError(ValueError):
    """Raised when an administrative feature definition is unsafe."""


class FeatureManager:
    """Evaluate and mutate feature definitions with cache invalidation and audit.

    The manager is dependency-injected with paths so tests and local operations
    never write to the repository's default runtime files accidentally.
    """

    def __init__(self, *, definition_file: Path = _DEFAULT_FILE, audit_file: Path | None = None):
        self._definition_file = definition_file
        self._audit_file = audit_file or definition_file.with_name("feature_management_audit.jsonl")
        self._lock = RLock()
        self._cached: dict[str, FeatureDefinition] | None = None
        self._cached_at = 0.0
        self._cached_mtime: int | None = None

    def evaluate(self, feature: str, context: FeatureContext | None = None) -> FeatureDecision:
        """Return one authoritative, fail-closed decision for a feature."""
        normalized = _normalize_name(feature)
        definitions = self._definitions()
        definition = definitions.get(normalized)
        if definition is None:
            return FeatureDecision(normalized, False, "unknown_feature")
        return self._evaluate_definition(
            definition, context or FeatureContext(), definitions, set()
        )

    def set_definition(self, definition: FeatureDefinition, *, actor: str) -> None:
        """Validate, persist, publish, and audit a feature-definition change."""
        _validate_definition(definition)
        with self._lock:
            definitions = self._definitions()
            definitions[definition.name] = definition
            self._write_definitions(definitions)
            self._publish(definitions)
            self._invalidate()
            self._audit(actor, "set_definition", definition.name, "success")

    def set_kill_switch(self, feature: str, enabled: bool, *, actor: str) -> None:
        """Apply an emergency switch without changing the rollout policy."""
        normalized = _normalize_name(feature)
        with self._lock:
            definitions = self._definitions()
            current = definitions.get(normalized)
            if current is None:
                self._audit(actor, "set_kill_switch", normalized, "unknown_feature")
                raise FeatureDefinitionError(f"unknown feature: {normalized}")
            definitions[normalized] = FeatureDefinition(
                **{**current.__dict__, "kill_switch": enabled}
            )
            self._write_definitions(definitions)
            self._publish(definitions)
            self._invalidate()
            self._audit(actor, "set_kill_switch", normalized, "success")

    def _evaluate_definition(
        self,
        definition: FeatureDefinition,
        context: FeatureContext,
        definitions: Mapping[str, FeatureDefinition],
        visiting: set[str],
    ) -> FeatureDecision:
        if definition.name in visiting:
            return FeatureDecision(definition.name, False, "dependency_cycle", definition.version)
        failure = _gate_failure(definition, context)
        if failure:
            return FeatureDecision(definition.name, False, failure, definition.version)
        next_visiting = {*visiting, definition.name}
        for dependency in definition.dependencies:
            required = definitions.get(dependency)
            if required is None:
                return FeatureDecision(
                    definition.name, False, "missing_dependency", definition.version
                )
            result = self._evaluate_definition(required, context, definitions, next_visiting)
            if not result.enabled:
                return FeatureDecision(
                    definition.name,
                    False,
                    f"dependency:{dependency}:{result.reason}",
                    definition.version,
                )
        if definition.rollout_percent < 100:
            bucket = _bucket(definition.name, context.user_id)
            if bucket >= definition.rollout_percent:
                return FeatureDecision(definition.name, False, "rollout", definition.version)
        return FeatureDecision(definition.name, True, "enabled", definition.version)

    def _definitions(self) -> dict[str, FeatureDefinition]:
        now = time.monotonic()
        mtime = _mtime(self._definition_file)
        with self._lock:
            if (
                self._cached is not None
                and now - self._cached_at < _CACHE_TTL_SECONDS
                and mtime == self._cached_mtime
            ):
                return dict(self._cached)
            loaded = self._read_definitions()
            self._cached = loaded
            self._cached_at = now
            self._cached_mtime = mtime
            return dict(loaded)

    def _read_definitions(self) -> dict[str, FeatureDefinition]:
        redis = get_redis()
        raw: object | None = None
        if redis is not None:
            try:
                raw = redis.get(_FEATURE_KEY)
            except Exception:
                raw = None
        if raw is None:
            try:
                raw = self._definition_file.read_text(encoding="utf-8")
            except OSError:
                return {}
        try:
            payload = json.loads(raw.decode() if isinstance(raw, bytes) else str(raw))
            items = payload.get("features", payload) if isinstance(payload, dict) else {}
            return {
                _normalize_name(name): _definition_from_mapping(name, value)
                for name, value in items.items()
                if isinstance(value, Mapping)
            }
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _write_definitions(self, definitions: Mapping[str, FeatureDefinition]) -> None:
        self._definition_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "features": {name: _definition_to_mapping(value) for name, value in definitions.items()}
        }
        temporary = self._definition_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self._definition_file)

    def _publish(self, definitions: Mapping[str, FeatureDefinition]) -> None:
        redis = get_redis()
        if redis is not None:
            try:
                payload = {
                    "features": {
                        name: _definition_to_mapping(value) for name, value in definitions.items()
                    }
                }
                redis.set(_FEATURE_KEY, json.dumps(payload, sort_keys=True))
            except Exception:
                return

    def _invalidate(self) -> None:
        self._cached = None
        self._cached_at = 0.0
        self._cached_mtime = None

    def _audit(self, actor: str, action: str, feature: str, outcome: str) -> None:
        self._audit_file.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": str(actor)[:128],
            "action": action,
            "feature": feature,
            "outcome": outcome,
        }
        with self._audit_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _normalize_name(name: str) -> str:
    normalized = str(name).strip().lower()
    if not normalized or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in normalized
    ):
        raise FeatureDefinitionError("feature names may contain only letters, numbers, '_' and '-'")
    return normalized


def _definition_from_mapping(name: str, value: Mapping[str, object]) -> FeatureDefinition:
    return FeatureDefinition(
        name=_normalize_name(name),
        owner=str(value.get("owner", "")),
        purpose=str(value.get("purpose", "")),
        enabled=value.get("enabled") is True,
        rollout_percent=int(value.get("rollout_percent", 0)),
        subscriptions=frozenset(str(item).lower() for item in value.get("subscriptions", [])),
        regions=frozenset(str(item).upper() for item in value.get("regions", [])),
        internal_only=value.get("internal_only") is True,
        beta_only=value.get("beta_only") is True,
        dependencies=tuple(_normalize_name(str(item)) for item in value.get("dependencies", [])),
        kill_switch=value.get("kill_switch") is True,
        version=str(value.get("version", "1")),
        expires_at=str(value["expires_at"]) if value.get("expires_at") else None,
        removal_issue=str(value["removal_issue"]) if value.get("removal_issue") else None,
    )


def _gate_failure(definition: FeatureDefinition, context: FeatureContext) -> str | None:
    """Return the first deterministic gate failure, or ``None`` when eligible."""
    if definition.kill_switch:
        return "kill_switch"
    if not definition.enabled:
        return "disabled"
    if definition.expires_at and _expired(definition.expires_at):
        return "expired"
    if definition.internal_only and not context.internal:
        return "internal_only"
    if definition.beta_only and not context.beta:
        return "beta_only"
    if definition.subscriptions and context.subscription.lower() not in definition.subscriptions:
        return "subscription"
    if definition.regions and context.region.upper() not in definition.regions:
        return "region"
    return None


def _definition_to_mapping(definition: FeatureDefinition) -> dict[str, object]:
    return {
        "owner": definition.owner,
        "purpose": definition.purpose,
        "enabled": definition.enabled,
        "rollout_percent": definition.rollout_percent,
        "subscriptions": sorted(definition.subscriptions),
        "regions": sorted(definition.regions),
        "internal_only": definition.internal_only,
        "beta_only": definition.beta_only,
        "dependencies": list(definition.dependencies),
        "kill_switch": definition.kill_switch,
        "version": definition.version,
        "expires_at": definition.expires_at,
        "removal_issue": definition.removal_issue,
    }


def _validate_definition(definition: FeatureDefinition) -> None:
    _normalize_name(definition.name)
    if not definition.owner or not definition.purpose:
        raise FeatureDefinitionError("owner and purpose are required")
    if not 0 <= definition.rollout_percent <= 100:
        raise FeatureDefinitionError("rollout_percent must be between 0 and 100")
    if definition.expires_at:
        _parse_timestamp(definition.expires_at)
    if not definition.removal_issue:
        raise FeatureDefinitionError("removal_issue is required")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise FeatureDefinitionError("expires_at must be an ISO-8601 timestamp") from error
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _expired(value: str) -> bool:
    return _parse_timestamp(value) <= datetime.now(timezone.utc)


def _bucket(feature: str, user_id: str) -> int:
    digest = hashlib.sha256(f"{feature}:{user_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 100


def _mtime(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


manager = FeatureManager()


def evaluate(feature: str, context: FeatureContext | None = None) -> FeatureDecision:
    """Evaluate a feature using the process-wide authoritative manager."""
    return manager.evaluate(feature, context)


def set_definition(definition: FeatureDefinition, *, actor: str) -> None:
    """Persist a feature definition through the process-wide manager."""
    manager.set_definition(definition, actor=actor)


def set_kill_switch(feature: str, enabled: bool, *, actor: str) -> None:
    """Change an emergency switch through the process-wide manager."""
    manager.set_kill_switch(feature, enabled, actor=actor)
