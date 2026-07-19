from pathlib import Path

from codes.app_modules.analysis_ui import (
    _build_analysis_content,
    _div_chart,
    _eps_chart,
    build_analysis_charts,
)


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
    assert "analysis-charts-summary" not in rendered
    assert rendered.count("analysis-charts-content") == 1
    assert "Dividend History" in rendered


def test_mockup_analysis_keeps_full_authoritative_detail_visible():
    rendered = str(_build_analysis_content({
        **_analysis(),
        "buffett": {
            "criteria": [{"label": "Moat durability", "score": 4, "max": 5}],
            "intrinsic_value": 96,
        },
        "quality": {
            "criteria": [{"label": "ROE", "score": 4, "max": 5}],
            "total_score": 84,
            "roe": 18,
        },
        "piotroski": {
            "f_score": 7,
            "label": "strong",
            "signals": [{"category": "Profitability", "signal": 1, "id": "F1", "label": "ROA positive", "note": "Pass"}],
        },
        "risk": {"beta": 1.1, "sharpe": 0.5, "n_years": 5, "risk_score": 60},
        "fcf_quality": {"fcf_quality_score": 81, "signal": "HIGH_CASH_QUALITY", "fcf": 10},
        "capital_allocation": {"capital_allocation_score": 77, "signal": "GOOD_ALLOCATOR", "roic": 12.1},
        "growth_quality": {"growth_quality_score": 74, "signal": "Bullish", "rev_cagr_10y": 12.3},
        "regime": {"regime": "BULL_LOW_VOL", "risk_level": "NORMAL", "comomentum_percentile": 82.4},
        "regime_overlay": {"regime_multiplier": 1.0},
        "factor_momentum": {"factor_momentum_score": 68, "signal": "Bullish"},
        "alternative_data": {"alternative_data_score": 55, "signal": "NEUTRAL", "status": "STUB"},
    }))

    for title in (
        "Intrinsic Value Estimate",
        "Economic Moat Rating",
        "Intrinsic Value Analysis",
        "Moat Rating Analysis",
        "Economic Moat Quality & Value",
        "Financial Health",
        "Stability Score (Bankruptcy Risk)",
        "FCF Quality",
        "Risk & Performance",
        "Market Regime",
        "CoMomentum Crowding",
        "Capital Allocation",
        "Growth Quality",
        "Momentum Analysis",
        "Factor Momentum",
        "Alternative Data",
        "Composite Score",
    ):
        assert title in rendered


def test_mockup_analysis_renders_available_charts_and_explains_summary_metrics(monkeypatch):
    monkeypatch.setattr(
        "codes.app_modules.analysis_ui.build_analysis_charts",
        lambda _data: ["rendered charts"],
    )
    data = {
        **_analysis(),
        "price_history": {"Close": {"0": 80, "1": 84}},
        "fcf_quality": {"fcf_quality_score": 81},
        "altman": {"z_score": 3.2, "zone_label": "Safe"},
    }

    rendered = str(_build_analysis_content(data))

    assert "rendered charts" in rendered
    assert "(fair value − price) ÷ price; not a return forecast" in rendered
    assert "Quality 84/100: ROE 18.0% and operating margin 14.0%." in rendered
    assert "Cash flow quality 81/100" in rendered


def test_eps_and_dividend_chart_overrides_merge_with_shared_layout(monkeypatch):
    """Chart-specific margins must not duplicate shared layout keywords."""
    datasets = {
        "eps_history": {
            "title": "ACME EPS History",
            "series": [{"x": ["2025", "2026"], "y": [2.0, 2.5]}],
        },
        "dividend_history": {
            "series": [
                {
                    "x": ["2025", "2026"],
                    "y": [100.0, 120.0],
                    "raw_y": [100.0, 120.0],
                }
            ],
        },
    }
    monkeypatch.setattr(
        "codes.app_modules.analysis_ui.chart_service.get_analysis_chart_dataset",
        lambda _data, chart_type: datasets[chart_type],
    )

    eps = _eps_chart([], "ACME")
    dividend = _div_chart([], "ACME")

    assert eps.figure.layout.margin.to_plotly_json() == {"l": 52, "r": 32, "t": 76, "b": 64}
    assert dividend.figure.layout.margin.to_plotly_json() == {
        "l": 56,
        "r": 32,
        "t": 28,
        "b": 64,
    }
    assert dividend.figure.layout.height == 420


def test_dividend_and_composite_history_share_the_second_chart_row(monkeypatch):
    """Shareholder-history charts pair on desktop and retain separate content."""
    monkeypatch.setattr(
        "codes.app_modules.analysis_ui._eps_chart", lambda *_args: "eps chart"
    )
    monkeypatch.setattr(
        "codes.app_modules.analysis_ui._price_chart", lambda *_args: "price chart"
    )
    monkeypatch.setattr(
        "codes.app_modules.analysis_ui._div_chart", lambda *_args: "dividend chart"
    )
    monkeypatch.setattr(
        "codes.app_modules.analysis_ui._score_history_chart",
        lambda *_args: "composite chart",
    )

    rows = build_analysis_charts({"symbol": "ACME", "graham": {}})

    assert len(rows) == 2
    assert rows[1].className == (
        "analysis-card-grid analysis-card-grid--two analysis-chart-history-pair"
    )
    assert rows[1].children == ["dividend chart", "composite chart"]


def test_mockup_analysis_styles_define_elevation_hover_and_chart_results_layout():
    styles = (ROOT / "assets/style/_analysis-mockup.scss").read_text()

    assert "box-shadow: var(--shadow-sm)" in styles
    assert ".analysis-mockup-factor-card:hover" in styles
    assert ".analysis-mockup-chart-results" in styles
    assert ".analysis-mockup-chart-results > .analysis-chart-results-stack" in styles
    assert "grid-column: 1 / -1" in styles
    assert "height: 360px !important" in styles
    assert "max-height: 420px" in styles
    assert ".analysis-chart-history-pair" in styles
    assert "@include media.reduced-motion" in styles
