from pathlib import Path


def test_security_workflow_contains_required_scanners():
    workflow = Path(".github/workflows/security-audit.yml").read_text().lower()
    for control in ("gitleaks", "pip-audit", "bandit", "npm audit", "cyclonedx"):
        assert control in workflow


def test_security_evidence_does_not_claim_external_assessment():
    evidence = Path("artifacts/production-proof/05-security/README.md").read_text()
    assert "Independent penetration test" in evidence
    assert "Open Release Blockers" in evidence
