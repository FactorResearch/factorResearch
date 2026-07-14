"""Engine contracts for the V0.5 architecture freeze.

An engine contract documents what an analysis engine accepts, returns, how it
validates inputs, and which product feature flags may execute it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FeatureFlag(str, Enum):
    INTERNAL = "internal"
    BETA = "beta"
    V1 = "v1"
    V2 = "v2"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class SchemaField:
    name: str
    types: tuple[type, ...]
    required: bool = True
    nullable: bool = False
    description: str = ""

    def type_names(self) -> list[str]:
        return [item.__name__ for item in self.types]


@dataclass(frozen=True)
class EngineSchema:
    fields: tuple[SchemaField, ...]

    def field_names(self) -> set[str]:
        return {field.name for field in self.fields}


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


@dataclass(frozen=True)
class EngineContract:
    name: str
    version: str
    input_schema: EngineSchema
    output_schema: EngineSchema
    interpretation_guide: str
    feature_flags: frozenset[FeatureFlag] = field(default_factory=lambda: frozenset({FeatureFlag.INTERNAL}))
    documentation: str = ""

    def supports(self, flag: FeatureFlag | str) -> bool:
        normalized = FeatureFlag(flag)
        return normalized in self.feature_flags


def validate_mapping(schema: EngineSchema, payload: dict[str, Any] | None) -> list[ValidationIssue]:
    """Validate a dict against required fields and basic Python types."""
    if not isinstance(payload, dict):
        return [ValidationIssue("__root__", "payload must be a dict")]

    issues: list[ValidationIssue] = []
    for field_def in schema.fields:
        if field_def.name not in payload:
            if field_def.required:
                issues.append(ValidationIssue(field_def.name, "missing required field"))
            continue

        value = payload[field_def.name]
        if value is None:
            if not field_def.nullable:
                issues.append(ValidationIssue(field_def.name, "field may not be null"))
            continue

        if not isinstance(value, field_def.types):
            expected = ", ".join(field_def.type_names())
            issues.append(ValidationIssue(field_def.name, f"expected type {expected}"))
    return issues


def validate_engine_input(contract: EngineContract, payload: dict[str, Any] | None) -> list[ValidationIssue]:
    return validate_mapping(contract.input_schema, payload)


def validate_engine_output(contract: EngineContract, payload: dict[str, Any] | None) -> list[ValidationIssue]:
    return validate_mapping(contract.output_schema, payload)


def assert_feature_enabled(contract: EngineContract, flag: FeatureFlag | str) -> None:
    """Raise PermissionError when a product tier cannot execute an engine."""
    if not contract.supports(flag):
        raise PermissionError(f"{contract.name} is not enabled for feature flag '{flag}'")


def contract_to_dict(contract: EngineContract) -> dict[str, Any]:
    """Serialize contract metadata for docs, API discovery, or tests."""
    def schema_to_list(schema: EngineSchema) -> list[dict[str, Any]]:
        return [
            {
                "name": field_def.name,
                "types": field_def.type_names(),
                "required": field_def.required,
                "nullable": field_def.nullable,
                "description": field_def.description,
            }
            for field_def in schema.fields
        ]

    return {
        "name": contract.name,
        "version": contract.version,
        "feature_flags": sorted(flag.value for flag in contract.feature_flags),
        "input_schema": schema_to_list(contract.input_schema),
        "output_schema": schema_to_list(contract.output_schema),
        "documentation": contract.documentation,
        "interpretation_guide": contract.interpretation_guide,
    }
