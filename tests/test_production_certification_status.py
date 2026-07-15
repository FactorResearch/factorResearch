from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "artifacts" / "production-proof"


def test_certification_fails_closed_while_external_proof_is_missing():
    status = (PROOF / "PRODUCTION_CERTIFICATION_STATUS.md").read_text()
    assert "NOT CERTIFIED FOR PUBLIC PRODUCTION LAUNCH" in status
    for phase in range(12):
        assert f"| {phase} " in status
    for blocker in ("external penetration", "production-size restores", "screen-reader", "legal", "paging"):
        assert blocker in status


def test_release_record_requires_all_independent_approvals():
    record = (PROOF / "release-certification-record.md").read_text()
    for approver in ("Engineering", "Operations", "Model Integrity", "Security", "Privacy/Legal", "Data Platform", "Accessibility", "Incident Commander"):
        assert approver in record
    assert "Final decision:** pending" in record
