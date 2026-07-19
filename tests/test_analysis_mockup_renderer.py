from pathlib import Path

from codes.app_modules.analysis_ui import _build_analysis_content


ROOT = Path(__file__).resolve().parents[1]


def _analysis() -> dict:
    return {
        "symbol": "ACME",
        "name": "Acme Corp",
        "sector": "Industrials",
        "market_code": "US",
        "price": 80,
        "updated_at": "2026-07-18",
        "graham": {"criteria": [], "pe": 12, "pb": 1.4, "graham_number": 96, "eps_history": []},
        "quality": {"criteria": [], "total_score": 84, "roe": 18, "op_margin": 14},
        "momentum": {"criteria": [], "total_score": 63},
        "enhanced": {"composite_score": 72, "verdict": "WATCH"},
        "buffett": {"intrinsic_value": 96, "net_margin": 10},
        "piotroski": {"f_score": 7, "gross_margin": 35},
        "altman": {"zone_label": "Safe", "z_score": 3.2},
        "risk": {"beta": 1.1, "sharpe": 0.5},
        "capital_allocation": {"roic": 12.1, "dividend_yield_implied": 1.2},
        "bias": {"bias": "outperform", "confidence": 0.7},
    }


def test_mockup_analysis_restores_all_factor_boxes_and_chart_contract():
    rendered = str(_build_analysis_content(_analysis()))

    for title in (
        "Z-Score Model",
        "Piotroski F-Score",
        "ROIC Quality Model",
        "Value Model (Intrinsic)",
        "Momentum Model",
        "Sentiment Model",
    ):
        assert title in rendered

    assert rendered.count("analysis-mockup-factor-card") == 6
    assert rendered.count("analysis-charts-summary") == 1
    assert rendered.count("analysis-charts-content") == 1
    assert "Dividend History" in rendered


def test_mockup_analysis_styles_define_elevation_hover_and_chart_results_layout():
    styles = (ROOT / "assets/style/_analysis-mockup.scss").read_text()

    assert "box-shadow: var(--shadow-sm)" in styles
    assert ".analysis-mockup-factor-card:hover" in styles
    assert ".analysis-mockup-chart-results" in styles
    assert "@include media.reduced-motion" in styles
