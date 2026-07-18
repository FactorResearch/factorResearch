"""Behavioral coverage for ISSUE_045 central configuration."""

from pathlib import Path

import pytest

from codes.services.configuration import (
    ConfigurationService,
    ConfigurationValidationError,
    SettingDefinition,
)


def _schema() -> tuple[SettingDefinition, ...]:
    return (
        SettingDefinition("SAFE_LIMIT", int, default=10, hot_reloadable=True, restart_required=False),
        SettingDefinition("DATABASE_URL", str, required=True, secret=True),
        SettingDefinition("WORKER_COUNT", int, default=2, restart_required=True),
    )


def test_required_values_are_typed_and_cached() -> None:
    source = {"DATABASE_URL": "postgresql://example", "SAFE_LIMIT": "20"}
    service = ConfigurationService(_schema(), source=source, cache_ttl_seconds=60)

    first = service.snapshot()
    source["SAFE_LIMIT"] = "99"

    assert first.get("SAFE_LIMIT") == 20
    assert service.get("SAFE_LIMIT") == 99


def test_invalid_reload_never_replaces_active_snapshot() -> None:
    source = {"DATABASE_URL": "postgresql://example", "SAFE_LIMIT": "20"}
    service = ConfigurationService(_schema(), source=source)
    assert service.get("SAFE_LIMIT") == 20
    source["SAFE_LIMIT"] = "not-an-int"

    with pytest.raises(ConfigurationValidationError):
        service.reload(actor="test")

    assert service.get("SAFE_LIMIT") == 20


def test_hot_reload_and_restart_required_changes_are_classified(tmp_path: Path) -> None:
    source = {"DATABASE_URL": "postgresql://example", "SAFE_LIMIT": "20", "WORKER_COUNT": "2"}
    service = ConfigurationService(_schema(), source=source, audit_file=tmp_path / "config-audit.jsonl")
    service.snapshot()
    source.update({"SAFE_LIMIT": "30", "WORKER_COUNT": "4"})

    change = service.reload(actor="ops")

    assert change.hot_reloaded == ("SAFE_LIMIT",)
    assert change.restart_required == ("WORKER_COUNT",)
    assert service.get("SAFE_LIMIT") == 30
    assert service.get("WORKER_COUNT") == 2
    assert service.snapshot().pending_restart == ("WORKER_COUNT",)
    assert "postgresql://example" not in (tmp_path / "config-audit.jsonl").read_text()


def test_rollback_restores_previous_valid_snapshot() -> None:
    source = {"DATABASE_URL": "postgresql://example", "SAFE_LIMIT": "20"}
    service = ConfigurationService(_schema(), source=source)
    first = service.snapshot()
    source["SAFE_LIMIT"] = "30"
    service.reload()

    restored = service.rollback(version=first.version)

    assert restored.get("SAFE_LIMIT") == 20
    assert service.audit_records()[-1]["action"] == "rollback"
