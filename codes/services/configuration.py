"""Validated, cached application configuration service for ISSUE_045.

This application-layer service is the authoritative boundary for operational
settings. It parses environment-style string values into typed values, keeps
the last valid snapshot active when a reload is invalid, and separates safe
hot-reloadable changes from settings that require a process restart.

The service does not persist secrets or configuration values. Optional audit
records contain setting names and change classification only.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Final

from codes.services.audit_journal import audit_journal

Parser = Callable[[str], object]


class ConfigurationError(ValueError):
    """Base error for invalid or unavailable configuration."""


class ConfigurationValidationError(ConfigurationError):
    """Raised when a candidate configuration cannot become active."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        details = "; ".join(f"{name}: {message}" for name, message in self.errors.items())
        super().__init__(f"configuration validation failed: {details}")


@dataclass(frozen=True)
class SettingDefinition:
    """Schema and lifecycle policy for one environment-backed setting."""

    name: str
    parser: Parser
    required: bool = False
    default: object | None = None
    secret: bool = False
    restart_required: bool = True
    hot_reloadable: bool = False
    allowed_values: tuple[object, ...] = ()
    owner: str = "platform"


@dataclass(frozen=True)
class ConfigurationSnapshot:
    """Immutable active configuration state with lifecycle metadata."""

    version: int
    values: Mapping[str, object]
    loaded_at: datetime
    pending_restart: tuple[str, ...] = ()

    def get(self, name: str) -> object:
        """Return a value from the active snapshot or raise a clear error."""
        try:
            return self.values[name]
        except KeyError as exc:
            raise ConfigurationError(f"unknown configuration setting: {name}") from exc


@dataclass(frozen=True)
class ConfigurationChange:
    """Summary of one accepted reload or rollback operation."""

    version: int
    changed: tuple[str, ...]
    hot_reloaded: tuple[str, ...]
    restart_required: tuple[str, ...]
    pending_restart: tuple[str, ...]


def _parse_bool(raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("expected true/false")


def _parse_int(raw: str) -> int:
    return int(raw.strip())


def _parse_float(raw: str) -> float:
    return float(raw.strip())


def _parse_csv(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw.split(",") if item.strip())


DEFAULT_DEFINITIONS: Final[tuple[SettingDefinition, ...]] = (
    SettingDefinition(
        "FLASK_ENV", str, default="development", restart_required=False,
        hot_reloadable=True, owner="web"
    ),
    SettingDefinition("APP_CACHE_DIR", str, default=None, owner="cache"),
    SettingDefinition("MAX_REQUEST_BYTES", _parse_int, default=2 * 1024 * 1024, owner="web"),
    SettingDefinition("TRUSTED_HOSTS", _parse_csv, default=(), owner="security"),
    SettingDefinition("PORT", _parse_int, default=8050, owner="web"),
    SettingDefinition(
        "DEFAULT_RATE_LIMIT", str, default="600 per minute", restart_required=False,
        hot_reloadable=True, owner="security"
    ),
    SettingDefinition(
        "TRAFFIC_OPTIONAL_RESERVE_RATIO", _parse_float, default=0.2,
        hot_reloadable=True, owner="security"
    ),
    SettingDefinition("REDIS_RETRY_SECONDS", _parse_float, default=5.0, hot_reloadable=True, owner="cache"),
    SettingDefinition("PROVIDER_TIMEOUT_SECONDS", _parse_float, default=8.0, hot_reloadable=True, owner="providers"),
    SettingDefinition("ANALYSIS_REFRESH_SECONDS", _parse_int, default=3600, hot_reloadable=True, owner="analysis-worker"),
    SettingDefinition("APP_FEATURE_FLAG", str, default="V1", owner="release"),
    SettingDefinition("FLASK_SECRET_KEY", str, secret=True, owner="security"),
    SettingDefinition("AUTH_TOKEN_SECRET", str, secret=True, owner="security"),
    SettingDefinition("ENCRYPTION_KEY", str, secret=True, owner="security"),
)


class ConfigurationService:
    """Own typed configuration snapshots and safe in-process reloads.

    A service instance is intended to be shared by one application process.
    The source is injected so tests and local tooling can validate a mapping
    without mutating the real process environment. Invalid candidates never
    replace a valid active snapshot.
    """

    def __init__(
        self,
        definitions: tuple[SettingDefinition, ...] = DEFAULT_DEFINITIONS,
        *,
        source: Mapping[str, str] | None = None,
        cache_ttl_seconds: float = 1.0,
        audit_file: Path | None = None,
    ) -> None:
        self._definitions = {definition.name: definition for definition in definitions}
        self._source = source if source is not None else os.environ
        self._cache_ttl_seconds = max(0.0, cache_ttl_seconds)
        self._audit_file = audit_file
        self._lock = RLock()
        self._active: ConfigurationSnapshot | None = None
        self._history: list[ConfigurationSnapshot] = []
        self._fingerprint: tuple[tuple[str, str | None], ...] | None = None
        self._cached_at = 0.0
        self._audit_records: list[dict[str, object]] = []

    def get(self, name: str) -> object:
        """Return a typed setting, refreshing the memory cache when needed."""
        with self._lock:
            self._ensure_current()
            assert self._active is not None
            return self._active.get(name)

    def snapshot(self) -> ConfigurationSnapshot:
        """Return the current immutable snapshot, loading it if necessary."""
        with self._lock:
            self._ensure_current()
            assert self._active is not None
            return self._active

    def reload(self, *, actor: str = "system") -> ConfigurationChange:
        """Validate the source and activate safe changes atomically.

        Restart-required changes remain pending while hot-reloadable changes
        become active immediately. Invalid candidates leave the active snapshot
        unchanged.
        """
        with self._lock:
            try:
                candidate = self._parse_source()
            except ConfigurationValidationError:
                # Remember the rejected source fingerprint so repeated runtime
                # lookups keep serving the last valid snapshot until the source
                # changes again or an operator explicitly retries reload.
                self._fingerprint = self._source_fingerprint()
                self._cached_at = time.monotonic()
                raise
            if self._active is None:
                snapshot = self._new_snapshot(candidate)
                self._active = snapshot
                self._history.append(snapshot)
                self._fingerprint = self._source_fingerprint()
                self._cached_at = time.monotonic()
                self._audit(actor, "load", (), (), "success")
                return ConfigurationChange(snapshot.version, tuple(candidate), (), (), ())

            current = dict(self._active.values)
            changed = tuple(sorted(name for name in candidate if candidate[name] != current.get(name)))
            hot = tuple(
                name for name in changed
                if self._definitions[name].hot_reloadable and not self._definitions[name].restart_required
            )
            restart = tuple(
                name for name in changed
                if self._definitions[name].restart_required or not self._definitions[name].hot_reloadable
            )
            active_values = {**current, **{name: candidate[name] for name in hot}}
            pending = tuple(sorted({*self._active.pending_restart, *restart}))
            snapshot = self._new_snapshot(active_values, pending_restart=pending)
            self._history.append(snapshot)
            self._active = snapshot
            self._fingerprint = self._source_fingerprint()
            self._cached_at = time.monotonic()
            self._audit(actor, "reload", hot, restart, "success")
            return ConfigurationChange(snapshot.version, changed, hot, restart, pending)

    def rollback(self, *, version: int | None = None, actor: str = "system") -> ConfigurationSnapshot:
        """Restore a prior valid snapshot and record the rollback without secrets."""
        with self._lock:
            if self._active is None:
                self._ensure_current()
            candidates = [item for item in self._history if item is not self._active]
            if version is not None:
                candidates = [item for item in candidates if item.version == version]
            if not candidates:
                raise ConfigurationError("no prior configuration snapshot available for rollback")
            restored = candidates[-1]
            self._active = self._new_snapshot(dict(restored.values), pending_restart=restored.pending_restart)
            self._history.append(self._active)
            self._cached_at = time.monotonic()
            self._audit(actor, "rollback", tuple(restored.values), (), "success")
            return self._active

    def audit_records(self) -> tuple[Mapping[str, object], ...]:
        """Return redacted in-memory audit records for diagnostics and tests."""
        with self._lock:
            return tuple(dict(record) for record in self._audit_records)

    def _ensure_current(self) -> None:
        fingerprint = self._source_fingerprint()
        if self._active is None or fingerprint != self._fingerprint:
            self.reload(actor="system")
            return
        if time.monotonic() - self._cached_at >= self._cache_ttl_seconds:
            # The source is unchanged, so refresh the cache timestamp without
            # reparsing every setting on each runtime lookup.
            self._cached_at = time.monotonic()

    def _parse_source(self) -> dict[str, object]:
        values: dict[str, object] = {}
        errors: dict[str, str] = {}
        for name, definition in self._definitions.items():
            raw = self._source.get(name)
            if raw is None or raw.strip() == "":
                if definition.default is not None or not definition.required:
                    values[name] = definition.default
                    continue
                errors[name] = "required value is missing"
                continue
            try:
                parsed = definition.parser(raw)
            except (TypeError, ValueError) as exc:
                errors[name] = str(exc)
                continue
            if definition.allowed_values and parsed not in definition.allowed_values:
                errors[name] = f"must be one of {definition.allowed_values!r}"
                continue
            values[name] = parsed
        if errors:
            raise ConfigurationValidationError(errors)
        return values

    def _new_snapshot(self, values: Mapping[str, object], *, pending_restart: tuple[str, ...] = ()) -> ConfigurationSnapshot:
        version = (self._history[-1].version + 1) if self._history else 1
        return ConfigurationSnapshot(version, dict(values), datetime.now(timezone.utc), tuple(sorted(pending_restart)))

    def _source_fingerprint(self) -> tuple[tuple[str, str | None], ...]:
        return tuple(sorted((name, self._source.get(name)) for name in self._definitions))

    def _audit(
        self,
        actor: str,
        action: str,
        hot_reloaded: tuple[str, ...],
        restart_required: tuple[str, ...],
        outcome: str,
    ) -> None:
        record: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": str(actor)[:128],
            "action": action,
            "hot_reloaded": list(hot_reloaded),
            "restart_required": list(restart_required),
            "outcome": outcome,
        }
        self._audit_records.append(record)
        if self._audit_file is None:
            return
        self._audit_file.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        audit_journal.record(
            "configuration",
            action=action,
            actor_id=actor,
            component="configuration",
            outcome=outcome,
            details={
                "hot_reloaded": list(hot_reloaded),
                "restart_required": list(restart_required),
            },
        )


def build_default_configuration_service() -> ConfigurationService:
    """Build the process-wide service using the current environment source."""
    return ConfigurationService()
