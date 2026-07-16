from pathlib import Path

from codes.app_modules import analysis_ui
from codes.app_modules.design_system.financial import data_trust_panel, methodology_disclosure
from codes.services import stock_analysis


ROOT = Path(__file__).resolve().parents[1]


def test_data_trust_panel_exposes_provenance_and_missing_effects():
    component = data_trust_panel({
        "generated_at": "2026-07-16T15:00:00+00:00",
        "provenance": {
            "price_timestamp": "Retrieved during this analysis",
            "filing_period": "2025-12-31",
            "source_category": "SEC EDGAR public filings",
            "currency": "USD",
            "normalization_status": "Canonical financial facts",
            "calculation_status": "cached",
            "model_scope": "Factor Research default models",
            "historical": True,
            "missing_effects": ["Momentum was skipped because price history is unavailable."],
        },
    })
    rendered = str(component)
    for label in (
        "Analysis date", "Market price", "Reporting period", "Source", "Currency",
        "Normalization", "Calculation", "Model", "Historical snapshot",
        "Missing-data effects", "not guarantees",
    ):
        assert label in rendered
    assert component.to_plotly_json()["props"]["data-trust-state"] == "partial"


def test_stock_analysis_provenance_distinguishes_quote_and_filing_dates(monkeypatch):
    monkeypatch.setattr(
        stock_analysis.db,
        "get_sec_facts_meta",
        lambda _symbol: {"latest_filing": "2025-10-31", "updated_at": "2025-11-01"},
    )
    provenance = stock_analysis._analysis_provenance(
        "AAPL",
        {
            "source_market": "US",
            "eps": [{"year": 2025, "value": 1}],
            "equity": [{"year": 2025, "value": 1}],
            "shares": [{"year": 2025, "value": 1}],
            "revenue": [],
            "op_cf": [],
            "capex": [],
        },
        price=200,
        defer_secondary=True,
    )
    assert provenance["filing_period"] == "2025-10-31"
    assert provenance["source_category"] == "SEC EDGAR public filings"
    assert provenance["currency"] == "USD"
    assert "provider quote time unavailable" in provenance["price_timestamp"]
    assert provenance["missing_inputs"] == ["revenue", "op_cf", "capex"]
    assert any("Optional signals are pending" in effect for effect in provenance["missing_effects"])


def test_cache_metadata_updates_trust_state_without_false_freshness():
    result = {
        "analysis_version": "old",
        "generated_at": "2020-01-01T00:00:00+00:00",
        "provenance": {},
    }
    stock_analysis._set_cache_metadata(result, True, "database")
    assert result["cache_stale"] is True
    assert result["provenance"]["calculation_status"] == "cached"
    assert result["provenance"]["historical"] is True


def test_methodology_is_inline_and_names_limitations():
    rendered = str(methodology_disclosure(
        "Graham",
        summary="Uses reported earnings and book value.",
        limitations="Missing inputs exclude the estimate.",
    ))
    assert "Graham methodology and limitations" in rendered
    assert "Missing inputs" in rendered
    scorecard = str(analysis_ui._render_scorecard(
        "Intrinsic Value", [{"label": "Test", "score": 1, "max": 2}], "graham"
    ))
    assert "methodology and limitations" in scorecard


def test_trust_patterns_cover_analyze_portfolio_factor_lab_and_screener():
    sources = "\n".join(
        (ROOT / path).read_text()
        for path in (
            "codes/app_modules/analysis_ui.py",
            "codes/app_modules/tabs/portfolio.py",
            "codes/app_modules/tabs/factor_lab.py",
            "codes/app_modules/tabs/screener.py",
        )
    )
    assert sources.count("data_trust_panel") >= 3
    assert "Mixed-currency conversion" in sources
    assert "User-customized factor weights" in sources
    assert "data_confidence" in sources


def test_marketing_copy_does_not_promise_investment_confidence():
    landing = (ROOT / "codes/templates/landing.html").read_text()
    assert "Invest with confidence" not in landing
    assert "decisions with confidence" not in landing
    assert "do not predict future performance" in landing

