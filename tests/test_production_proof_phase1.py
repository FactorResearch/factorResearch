from pathlib import Path


def test_pr_workflow_runs_locked_release_gate():
    workflow = Path(".github/workflows/pr-tests.yml").read_text()
    gate = Path("scripts/release-gate.sh").read_text()
    assert "./scripts/release-gate.sh" in workflow
    assert "pytest -q" in gate
    assert "coverage run --source=codes" in gate
    assert "python -m compileall" in gate
    assert "python -m pip_audit -r requirements.txt --strict" in gate
    assert "-r requirements-proof.txt" in workflow
    assert "node --check" in gate
    assert "npx --no-install sass" in gate
    assert "npx --yes" not in gate


def test_release_gate_checks_tracked_runtime_css():
    gate = Path("scripts/release-gate.sh").read_text()
    ignore = Path(".gitignore").read_text()
    for asset in ("style.css", "company_analysis.css", "error_pages.css"):
        assert f"assets/{asset}" in gate
        assert f"!assets/{asset}" in ignore


def test_phase1_evidence_records_external_certification_gaps():
    evidence = Path("artifacts/production-proof/01-release-integrity/README.md").read_text()
    assert "20 consecutive" in evidence
    assert "production preflight" in evidence
    assert "PostgreSQL/Redis integration" in evidence
