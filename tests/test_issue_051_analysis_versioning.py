"""Acceptance tests for ISSUE_051 immutable analysis manifests."""

from codes.services.analysis_manifest import build_manifest, compatibility


def test_manifest_contains_methodology_and_lineage_versions() -> None:
    manifest = build_manifest(
        "analysis-v2", {"quality": "3", "graham": "2"}, market_code="US",
        provenance={"source_category": "SEC EDGAR", "filing_period": "2025-12-31"},
    )
    assert manifest["model_versions"] == {"graham": "2", "quality": "3"}
    assert manifest["source_category"] == "SEC EDGAR"
    assert manifest["filing_period"] == "2025-12-31"
    assert manifest["normalization_version"] == "canonical-v1"


def test_incompatible_manifests_cannot_be_compared() -> None:
    base = build_manifest("analysis-v1", {"quality": "1"}, market_code="US")
    changed = {**base, "model_versions": {"quality": "2"}}
    assert compatibility(base, changed) == (False, ("model_versions",))
    assert compatibility({}, base) == (True, ())
