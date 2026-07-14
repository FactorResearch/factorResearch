from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_browser_audit_covers_required_modes_and_failures():
    audit = (ROOT / "scripts" / "audit-accessibility.mjs").read_text()
    for requirement in ("wcag22a", "wcag22aa", "themes = ['light', 'dark']", "mobile-200-percent", "overflow > 1", "prefers-reduced-motion"):
        assert requirement in audit
    assert "10-accessibility/axe-results.json" in audit


def test_manual_matrix_keeps_nonautomatable_checks_visible():
    matrix = (ROOT / "artifacts" / "production-proof" / "10-accessibility" / "manual-matrix.md").read_text()
    for workflow in ("quick peek", "Analyze", "Portfolio", "Authentication", "Terms/privacy"):
        assert workflow in matrix
    assert matrix.count("pending") >= 20
