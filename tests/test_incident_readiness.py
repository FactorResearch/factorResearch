from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "artifacts" / "production-proof" / "11-incidents"


def test_incident_program_has_roles_deadlines_and_authority():
    matrix = (EVIDENCE / "severity-matrix.md").read_text()
    for requirement in ("SEV-1", "5 minutes", "incident commander", "security/privacy", "payments", "read-only mode"):
        assert requirement in matrix


def test_incident_record_requires_actionable_evidence():
    template = (EVIDENCE / "incident-template.md").read_text()
    for requirement in ("Affected users", "Detection source", "Timeline", "Decisions", "owner", "due date", "verification method"):
        assert requirement in template


def test_game_days_cover_availability_and_security_data():
    scenarios = (EVIDENCE / "game-day-scenarios.md").read_text()
    for requirement in ("Database Saturation", "Leaked Provider Credential", "acknowledged within 5 minutes", "provenance", "repeat findings block release"):
        assert requirement in scenarios
