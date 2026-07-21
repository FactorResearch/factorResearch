from pathlib import Path


def test_security_workflow_contains_required_scanners():
    workflow = Path(".github/workflows/security-audit.yml").read_text().lower()
    for control in ("gitleaks", "pip-audit", "bandit", "npm audit", "cyclonedx"):
        assert control in workflow
    assert "sbom-python.json" in workflow
    assert "sbom-node.json" in workflow
    assert "uv sync --frozen" in workflow


def test_dependency_review_blocks_vulnerabilities_and_prohibited_licenses():
    workflow = Path(".github/workflows/dependency-review.yml").read_text().lower()
    assert "actions/dependency-review-action@v5" in workflow
    assert "fail-on-severity: high" in workflow
    assert "license-check: true" in workflow
    assert "agpl-3.0" in workflow


def test_security_evidence_does_not_claim_external_assessment():
    evidence = Path("artifacts/production-proof/05-security/README.md").read_text()
    assert "Independent penetration test" in evidence
    assert "Open Release Blockers" in evidence
