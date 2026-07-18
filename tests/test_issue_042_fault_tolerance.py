"""Regression coverage for ISSUE_042 section-level fault isolation."""

from __future__ import annotations

from codes.app_modules import analysis_ui


def test_failed_analysis_card_preserves_sibling_sections(monkeypatch) -> None:
    def broken(_data):
        raise RuntimeError("optional model failed")

    monkeypatch.setattr(analysis_ui, "_risk_card", broken)
    data = {
        "symbol": "NULL",
        "name": "Nullable Corp",
        "sector": "Unknown",
        "price": None,
        "graham": {"criteria": [], "pe": None, "pb": None, "eps_history": []},
        "quality": {"criteria": [], "roe": None, "op_margin": None},
        "momentum": {"criteria": []},
        "enhanced": {"composite_score": 50, "verdict": "WATCH"},
        "risk": {"beta": None, "sharpe": None},
    }

    rendered = str(analysis_ui._build_analysis_content(data))

    assert "Quick Research Snapshot" in rendered
    assert "Valuation" in rendered
    assert "Risk is temporarily unavailable" in rendered
    assert "analysis-risk-retry" in rendered
