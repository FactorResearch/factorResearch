"""Immutable methodology manifests for reproducible analyses (ISSUE_051)."""

from __future__ import annotations

from typing import Any

MANIFEST_VERSION = "1"
PLATFORM_VERSION = "2026.07"
NORMALIZATION_VERSION = "canonical-v1"
PROVIDER_MAPPING_VERSION = "provider-map-v1"


def build_manifest(
    analysis_version: str,
    model_versions: dict[str, str],
    *,
    market_code: str,
    provenance: dict[str, Any] | None = None,
    configuration_version: str = "default",
) -> dict[str, Any]:
    """Build a stable, JSON-safe manifest for one completed analysis."""
    source = provenance or {}
    return {
        "manifest_version": MANIFEST_VERSION,
        "platform_version": PLATFORM_VERSION,
        "analysis_version": str(analysis_version),
        "model_versions": {key: str(model_versions[key]) for key in sorted(model_versions)},
        "normalization_version": str(source.get("normalization_version") or NORMALIZATION_VERSION),
        "provider_mapping_version": PROVIDER_MAPPING_VERSION,
        "configuration_version": str(configuration_version),
        "market_code": str(market_code),
        "source_category": str(source.get("source_category") or "unknown"),
        "filing_period": source.get("filing_period"),
    }


def compatibility(manifest: dict[str, Any] | None, other: dict[str, Any] | None) -> tuple[bool, tuple[str, ...]]:
    """Return whether two analyses may be compared safely."""
    if not manifest or not other:
        return True, ()  # Legacy snapshots predate manifest persistence.
    reasons = tuple(
        key for key in (
            "manifest_version", "analysis_version", "model_versions",
            "normalization_version", "provider_mapping_version", "market_code",
        ) if manifest.get(key) != other.get(key)
    )
    return not reasons, reasons
