from codes.app_modules.analysis_ui import _build_analysis_content


def test_cached_analysis_renders_nullable_valuation_and_risk_metrics():
    data = {
        "symbol": "NULL",
        "name": "Nullable Corp",
        "sector": "Unknown",
        "price": None,
        "graham": {"criteria": [], "pe": None, "pb": None, "eps_history": []},
        "quality": {"criteria": [], "roe": None, "op_margin": None},
        "momentum": {"criteria": []},
        "enhanced": {
            "composite_score": 50,
            "verdict": "WATCH",
            "verdict_label": "watch",
        },
        "risk": {"beta": None, "sharpe": None},
    }

    rendered = str(_build_analysis_content(data))

    assert "P/E N/A" in rendered
    assert "P/B N/A" in rendered
    assert "Beta N/A" in rendered
    assert "Sharpe N/A" in rendered
