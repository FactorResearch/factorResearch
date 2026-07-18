"""Acceptance tests for ISSUE_044 feature management."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codes.services.feature_management import (
    FeatureContext,
    FeatureDefinition,
    FeatureDefinitionError,
    FeatureManager,
)


def _definition(name: str = "new-search", **changes: object) -> FeatureDefinition:
    values: dict[str, object] = {
        "name": name,
        "owner": "platform",
        "purpose": "controlled search rollout",
        "enabled": True,
        "rollout_percent": 100,
        "removal_issue": "ISSUE_044",
    }
    values.update(changes)
    return FeatureDefinition(**values)


def test_missing_feature_defaults_to_disabled(tmp_path: Path) -> None:
    manager = FeatureManager(definition_file=tmp_path / "features.json")
    decision = manager.evaluate("missing", FeatureContext(user_id="u1"))
    assert (decision.enabled, decision.reason) == (False, "unknown_feature")


def test_rollout_subscription_region_beta_and_internal_gates(tmp_path: Path) -> None:
    manager = FeatureManager(definition_file=tmp_path / "features.json")
    manager.set_definition(
        _definition(
            subscriptions=frozenset({"premium"}),
            regions=frozenset({"CA"}),
            beta_only=True,
            internal_only=True,
        ),
        actor="admin",
    )
    denied = manager.evaluate(
        "new-search", FeatureContext(user_id="u1", subscription="free", region="US")
    )
    allowed = manager.evaluate(
        "new-search",
        FeatureContext(user_id="u1", subscription="premium", region="ca", beta=True, internal=True),
    )
    assert denied.enabled is False
    assert allowed.enabled is True


def test_dependencies_and_kill_switch_fail_closed_and_audit_changes(tmp_path: Path) -> None:
    definition_file = tmp_path / "features.json"
    audit_file = tmp_path / "audit.jsonl"
    manager = FeatureManager(definition_file=definition_file, audit_file=audit_file)
    manager.set_definition(_definition("base"), actor="admin")
    manager.set_definition(_definition("dependent", dependencies=("base",)), actor="admin")
    manager.set_kill_switch("base", True, actor="ops")
    decision = manager.evaluate("dependent", FeatureContext(user_id="u1"))
    assert decision.reason == "dependency:base:kill_switch"
    records = [json.loads(line) for line in audit_file.read_text().splitlines()]
    assert [record["action"] for record in records] == [
        "set_definition",
        "set_definition",
        "set_kill_switch",
    ]


def test_invalid_definition_never_becomes_active(tmp_path: Path) -> None:
    manager = FeatureManager(definition_file=tmp_path / "features.json")
    with pytest.raises(FeatureDefinitionError):
        manager.set_definition(_definition(rollout_percent=101), actor="admin")
    assert manager.evaluate("new-search").enabled is False
