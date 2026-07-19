from pathlib import Path

from codes.app_modules.analysis_ui import (
    _build_analysis_content,
    analysis_score_drivers,
    critical_analysis_warnings,
)
from codes.app_modules.tabs.portfolio import portfolio_health_snapshot


ROOT = Path(__file__).resolve().parents[1]


def _analysis():
    return {
        "symbol": "ACME",
        "name": "Acme Corp",
        "sector": "Industrials",
        "price": 80,
        "updated_at": "2026-07-16",
        "graham": {
            "criteria": [],
            "pe": 12,
            "pb": 1.4,
            "total_score": 72,
            "total_max": 100,
            "eps_history": [],
        },
        "quality": {
            "criteria": [],
            "roe": 18,
            "op_margin": 14,
            "total_score": 84,
            "total_max": 100,
        },
        "momentum": {"criteria": [], "total_score": 38, "total_max": 100},
        "enhanced": {"composite_score": 66, "verdict": "WATCH", "verdict_label": "watch"},
        "risk": {"beta": 1.1, "sharpe": 0.5},
        "piotroski": {"f_score": 3},
        "altman": {"zone_label": "Distress"},
        "fcf_quality": {"fcf_quality_score": 75},
        "growth_quality": {"growth_quality_score": 61},
    }


def test_analyze_first_view_states_conclusion_weakest_risk_and_freshness_in_order():
    rendered = str(_build_analysis_content(_analysis()))
    labels = ["Primary conclusion", "Strongest driver", "Weakest factor", "Key risk", "Data freshness"]
    positions = [rendered.index(label) for label in labels]
    assert positions == sorted(positions)
    assert "Momentum is the weakest measured factor at 38/100" in rendered
    assert "role='alert'" in rendered
    assert "Critical warning" in rendered


def test_analyze_drivers_and_critical_warnings_are_deterministic():
    positive, weak = analysis_score_drivers(_analysis())
    assert positive[0] == ("Quality", 84.0)
    assert weak[0] == ("Momentum", 38.0)
    assert critical_analysis_warnings(_analysis()) == [
        "Balance-sheet model is in the Altman distress zone.",
        "Accounting strength is weak at F-Score 3/9.",
    ]


def test_disclosures_restore_session_state_and_browser_navigation():
    javascript = (ROOT / "assets/design_system.js").read_text()
    rendered = str(_build_analysis_content(_analysis()))
    assert "data-persist-disclosure='true'" in rendered
    assert "data-disclosure-key='ACME:analysis-valuation'" in rendered
    assert "sessionStorage" in javascript
    assert "popstate" in javascript
    assert "pageshow" in javascript
    assert "aria-current" in javascript


def test_portfolio_leads_with_health_concentration_coverage_and_weak_link():
    holdings = {
        "AAA": {"shares": 8, "price_at_add": 100, "current_price": 100},
        "BBB": {"shares": 2, "price_at_add": 100, "current_price": 100},
    }
    entries = {
        "AAA": {"updated_at": "2026-07-16", "data": {"composite_score": 78, "sector": "Tech"}},
        "BBB": {"updated_at": "2026-07-15", "data": {"composite_score": 42, "sector": "Health"}},
    }
    snapshot = portfolio_health_snapshot(holdings, entries)
    assert snapshot["health"] == "Mixed"
    assert snapshot["coverage"] == 100
    assert snapshot["largest"]["symbol"] == "AAA"
    assert snapshot["weak_link"]["symbol"] == "BBB"
    assert snapshot["risks"][0].startswith("AAA is 80.0%")


def test_portfolio_research_weak_link_requires_a_unique_peer_low():
    """Tied scores and a lone researched holding must not create an arbitrary weak link."""
    holdings = {
        "AAA": {"shares": 1, "price_at_add": 100, "current_price": 100},
        "BBB": {"shares": 1, "price_at_add": 100, "current_price": 100},
    }
    tied_entries = {
        "AAA": {"data": {"composite_score": 40, "sector": "Tech"}},
        "BBB": {"data": {"composite_score": 40, "sector": "Health"}},
    }

    assert portfolio_health_snapshot(holdings, tied_entries)["weak_link"] is None
    assert portfolio_health_snapshot(holdings, {"AAA": tied_entries["AAA"]})["weak_link"] is None
