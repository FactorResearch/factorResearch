"""Regression checks for ISSUE_065's public API compatibility policy."""

from __future__ import annotations

import json
from pathlib import Path

from codes.api.compatibility import find_breaking_changes, find_invalid_deprecations

ROOT = Path(__file__).resolve().parents[2]


def _contract() -> dict:
    return json.loads((ROOT / "openapi.yaml").read_text(encoding="utf-8"))


def test_current_v1_contract_matches_supported_baseline() -> None:
    baseline = json.loads(
        (ROOT / "tests/api/fixtures/openapi-v1-baseline.json").read_text(encoding="utf-8")
    )
    contract = _contract()
    assert find_breaking_changes(baseline, contract) == []
    assert find_invalid_deprecations(contract) == []


def test_lifecycle_metadata_declares_support_window() -> None:
    lifecycle = _contract()["x-api-lifecycle"]
    assert lifecycle["current_version"] == "v1"
    assert lifecycle["supported_versions"] == ["v1"]
    assert lifecycle["previous_major_support_months"] == 12
    assert lifecycle["deprecation_notice_months"] == 6
    assert lifecycle["policy"] == "docs/api-versioning.md"


def test_removed_fields_are_breaking_changes() -> None:
    baseline = {
        "components": {
            "schemas": {"Thing": {"type": "object", "properties": {"id": {"type": "string"}}}}
        }
    }
    current = {"components": {"schemas": {"Thing": {"type": "object", "properties": {}}}}}
    assert "components.schemas.Thing.id: field removed" in find_breaking_changes(baseline, current)


def test_deprecated_items_require_replacement_and_removal_version() -> None:
    contract = {"paths": {"/old": {"get": {"deprecated": True}}}}
    violations = find_invalid_deprecations(contract)
    assert len(violations) == 3
