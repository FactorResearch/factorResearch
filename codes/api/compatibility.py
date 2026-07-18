"""Compatibility checks for the checked-in public OpenAPI contracts.

The checker compares a current contract with the oldest supported v1 baseline.
It intentionally applies conservative rules: clients may ignore new response
fields, but an existing field or constraint cannot be removed or changed.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping

import yaml

JsonObject = dict[str, object]


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _schema_changes(
    baseline: Mapping[str, object], current: Mapping[str, object], location: str
) -> list[str]:
    changes: list[str] = []
    if baseline.get("$ref") != current.get("$ref"):
        if "$ref" in baseline or "$ref" in current:
            changes.append(f"{location}: schema reference changed")
        return changes
    for key in ("type", "format", "nullable", "const", "additionalProperties"):
        if key in baseline and baseline.get(key) != current.get(key):
            changes.append(f"{location}: {key} changed")
    if "enum" in baseline and baseline.get("enum") != current.get("enum"):
        changes.append(f"{location}: enum values changed")
    baseline_required = set(baseline.get("required", []))
    current_required = set(current.get("required", []))
    if baseline_required != current_required:
        changes.append(f"{location}: required fields changed")
    baseline_properties = _mapping(baseline.get("properties"))
    current_properties = _mapping(current.get("properties"))
    for name, schema in baseline_properties.items():
        if name not in current_properties:
            changes.append(f"{location}.{name}: field removed")
            continue
        changes.extend(
            _schema_changes(
                _mapping(schema), _mapping(current_properties[name]), f"{location}.{name}"
            )
        )
    if "items" in baseline:
        changes.extend(
            _schema_changes(
                _mapping(baseline.get("items")),
                _mapping(current.get("items")),
                f"{location}[]",
            )
        )
    return changes


def _response_changes(
    baseline_response: Mapping[str, object],
    current_response: Mapping[str, object],
    location: str,
) -> list[str]:
    """Compare one response's media types and payload schema."""
    changes: list[str] = []
    baseline_content = _mapping(baseline_response.get("content"))
    current_content = _mapping(current_response.get("content"))
    for media_type, baseline_media in baseline_content.items():
        if media_type not in current_content:
            changes.append(f"{location}: media type removed")
            continue
        baseline_schema = _mapping(_mapping(baseline_media).get("schema"))
        current_schema = _mapping(_mapping(current_content[media_type]).get("schema"))
        changes.extend(
            _schema_changes(
                baseline_schema,
                current_schema,
                f"{location}.{media_type}",
            )
        )
    return changes


def _operation_changes(
    baseline_operation: Mapping[str, object],
    current_operation: Mapping[str, object],
    location: str,
) -> list[str]:
    """Compare an operation's identity and response surface."""
    changes: list[str] = []
    if baseline_operation.get("operationId") != current_operation.get("operationId"):
        changes.append(f"{location}: operationId changed")
    baseline_responses = _mapping(baseline_operation.get("responses"))
    current_responses = _mapping(current_operation.get("responses"))
    for status, baseline_response in baseline_responses.items():
        response_location = f"{location}.{status}"
        if status not in current_responses:
            changes.append(f"{response_location}: response removed")
            continue
        changes.extend(
            _response_changes(
                _mapping(baseline_response),
                _mapping(current_responses[status]),
                response_location,
            )
        )
    return changes


def _path_changes(
    baseline_path: Mapping[str, object], current_path: Mapping[str, object], path: str
) -> list[str]:
    """Compare all supported operations under one path."""
    changes: list[str] = []
    for method, baseline_operation in baseline_path.items():
        if method.startswith("x-"):
            continue
        location = f"paths.{path}.{method}"
        if method not in current_path:
            changes.append(f"{location}: operation removed")
            continue
        changes.extend(
            _operation_changes(
                _mapping(baseline_operation), _mapping(current_path[method]), location
            )
        )
    return changes


def find_breaking_changes(
    baseline: Mapping[str, object], current: Mapping[str, object]
) -> list[str]:
    """Return active-contract changes that can break an existing client.

    Args:
        baseline: The oldest supported OpenAPI document.
        current: The OpenAPI document being reviewed.

    Returns:
        Human-readable compatibility violations. An empty list means the
        current contract is compatible with the baseline.
    """
    changes: list[str] = []
    baseline_paths = _mapping(baseline.get("paths"))
    current_paths = _mapping(current.get("paths"))
    for path, baseline_path in baseline_paths.items():
        if path not in current_paths:
            changes.append(f"paths.{path}: path removed")
            continue
        changes.extend(_path_changes(_mapping(baseline_path), _mapping(current_paths[path]), path))
    baseline_schemas = _mapping(_mapping(baseline.get("components")).get("schemas"))
    current_schemas = _mapping(_mapping(current.get("components")).get("schemas"))
    for name, baseline_schema in baseline_schemas.items():
        if name not in current_schemas:
            changes.append(f"components.schemas.{name}: schema removed")
            continue
        changes.extend(
            _schema_changes(
                _mapping(baseline_schema),
                _mapping(current_schemas[name]),
                f"components.schemas.{name}",
            )
        )
    return changes


def find_invalid_deprecations(contract: Mapping[str, object]) -> list[str]:
    """Return deprecated OpenAPI items missing required migration guidance."""
    invalid: list[str] = []

    def visit(value: object, location: str) -> None:
        if isinstance(value, Mapping):
            if value.get("deprecated") is True:
                metadata = _mapping(value.get("x-deprecation"))
                for key in ("replacement", "removal_version", "notice"):
                    if not isinstance(metadata.get(key), str) or not metadata[key].strip():
                        invalid.append(f"{location}: missing x-deprecation.{key}")
            for key, child in value.items():
                visit(child, f"{location}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{location}[{index}]")

    visit(contract, "openapi")
    return invalid


def _load(path: Path) -> JsonObject:
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain an OpenAPI object")
    return loaded


def main() -> int:
    """Run the compatibility check from the repository root."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", type=Path, default=Path("tests/api/fixtures/openapi-v1-baseline.json")
    )
    parser.add_argument("--current", type=Path, default=Path("openapi.yaml"))
    args = parser.parse_args()
    violations = find_breaking_changes(_load(args.baseline), _load(args.current))
    violations.extend(find_invalid_deprecations(_load(args.current)))
    if violations:
        print("API compatibility check failed:")
        print("\n".join(f"- {violation}" for violation in violations))
        return 1
    print(f"API compatibility check passed: {args.current} vs {args.baseline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
