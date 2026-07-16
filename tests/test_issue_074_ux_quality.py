import json
from collections import deque
from pathlib import Path

from codes.services import performance_metrics, product_analytics


ROOT = Path(__file__).resolve().parents[1]


def test_web_vitals_are_segmented_and_budgeted(monkeypatch):
    monkeypatch.setattr(performance_metrics, "_web_vitals", deque(maxlen=20))
    assert performance_metrics.record_web_vital(
        "LCP", 2400, route="/", device="mobile"
    )
    assert performance_metrics.record_web_vital(
        "INP", 250, route="/", device="mobile"
    )
    assert performance_metrics.record_web_vital(
        "CLS", 0.05, route="/", device="desktop"
    )
    assert not performance_metrics.record_web_vital(
        "FID", 10, route="/", device="desktop"
    )
    result = performance_metrics.snapshot()["web_vitals"]
    assert result["segments"]["mobile:/:LCP"]["passing"] is True
    assert result["segments"]["mobile:/:INP"]["passing"] is False
    assert result["regressions"] == ["mobile:/:INP"]


def test_product_telemetry_drops_sensitive_financial_dimensions():
    safe = product_analytics.sanitize_metadata({
        "symbol": "AAPL",
        "portfolio_name": "Retirement",
        "shares": 100,
        "formula": "secret formula",
        "source": "analysis",
        "duration_ms": 123.456,
        "sections": ["one", "two"],
    })
    assert safe == {
        "source": "analysis",
        "duration_ms": 123.46,
        "sections_count": 2,
    }
    assert product_analytics.normalize_page_path("/AAPL/analyze/20260716") == "/company/analyze/date"
    assert product_analytics.normalize_page_path("/analyze/MSFT?secret=yes") == "/analyze/company"


def test_browser_telemetry_collects_current_vitals_without_values_or_replay():
    source = (ROOT / "assets/ux_telemetry.js").read_text()
    for contract in (
        "largest-contentful-paint", "layout-shift", "interactionId",
        "/analytics/vitals", "deviceClass", "navigation_type",
        "model_detail_expanded", "methodology_opened", "form_validation_failure",
    ):
        assert contract in source
    assert "event.target.value" not in source

    bootstrap = (ROOT / "codes/services/analytics_bootstrap.py").read_text()
    assert "autocapture:false" in bootstrap
    assert "disable_session_recording:true" in bootstrap
    assert "ENABLE_MASKED_SESSION_REPLAY" in bootstrap
    assert "data-clarity-mask" in bootstrap


def test_performance_budgets_and_release_evidence_are_enforced():
    budgets = json.loads((ROOT / "config/ux_performance_budgets.json").read_text())
    assert budgets["core_web_vitals_p75"] == {"LCP_ms": 2500, "INP_ms": 200, "CLS": 0.1}
    assert "cached_analysis_first_useful" in budgets["task_completion_ms"]
    release_gate = (ROOT / "scripts/release-gate.sh").read_text()
    workflow = (ROOT / ".github/workflows/pr-tests.yml").read_text()
    assert "check-ux-performance-budgets.py" in release_gate
    assert "ux-performance-budget-report.json" in workflow


def test_usability_study_and_numbered_findings_cover_critical_tasks():
    study = (ROOT / "artifacts/production-proof/11-ux-quality/usability-study.md").read_text()
    findings = (ROOT / "artifacts/production-proof/11-ux-quality/findings-log.csv").read_text()
    review = (ROOT / "artifacts/production-proof/11-ux-quality/ux-release-review.md").read_text()
    for task in (
        "Identify the conclusion", "Explain why", "Identify the weakest factor",
        "Verify freshness", "Compare two companies", "Diagnose portfolio risk",
        "Recover from a failed section",
    ):
        assert task in study
    assert "Less-experienced investor" in study
    assert "Advanced/professional user" in study
    assert "UX-001" in findings and "ISSUE_074" in findings
    assert "Accessibility and responsive audit" in review
    assert "Privacy review" in review

