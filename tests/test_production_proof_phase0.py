from pathlib import Path


BASELINE = Path("artifacts/production-proof/00-baseline")
REQUIRED = {
    "README.md": ("Certification Checklist", "Evidence Set"),
    "ownership.md": ("Interim Assignments", "Decision Rules"),
    "architecture.md": ("Trust Boundaries", "Data Classification"),
    "service-inventory.md": ("Deployable Processes", "External Dependencies"),
    "capacity-assumptions.md": ("Launch Workload Envelope", "Resource Guardrails"),
    "risk-register.md": ("R-001", "Review Rules"),
}


def test_phase0_evidence_contract_is_complete():
    for filename, markers in REQUIRED.items():
        content = (BASELINE / filename).read_text()
        assert all(marker in content for marker in markers), filename


def test_phase0_records_required_runtime_boundaries():
    inventory = (BASELINE / "service-inventory.md").read_text()
    for dependency in ("PostgreSQL", "Redis", "SEC EDGAR", "Auth0", "Stripe"):
        assert dependency in inventory


def test_phase0_risks_have_unique_ids_and_owners():
    rows = [line for line in (BASELINE / "risk-register.md").read_text().splitlines() if line.startswith("| R-")]
    ids = [row.split("|")[1].strip() for row in rows]
    assert len(ids) >= 15
    assert len(ids) == len(set(ids))
    assert all(row.split("|")[-2].strip() for row in rows)
