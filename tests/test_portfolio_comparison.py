"""
Tests for compare_portfolios() — Portfolio Page Refactor (multi-portfolio
comparison service).

Verifies:
1. Returns error when either portfolio's simulation errors.
2. Picks the higher-scoring portfolio as winner with correct reasons.
3. Returns winner=None with "similar" message when scores are close.
4. _weak_link_score returns 100 when no holdings are weak links.
5. _weak_link_score returns neutral 50 on analyze_weak_links error / empty.
"""

import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from codes import portfolio


def _sim(cagr, spy_cagr, final_value, p50_last):
    return {
        "error": None,
        "backtest": {
            "error": None,
            "cagr": cagr,
            "spy_cagr": spy_cagr,
            "final_value": final_value,
        },
        "montecarlo": {"error": None, "p50": [final_value, p50_last]},
        "holdings": {},
    }


class TestCompareePortfoliosErrors:
    def test_error_from_sim_a_propagates(self):
        with patch.object(portfolio, "run_simulation",
                          side_effect=lambda n: {"error": "boom"} if n == "A" else _sim(10, 8, 100, 110)):
            result = portfolio.compare_portfolios("A", "B")
        assert result["error"] == "boom"

    def test_error_from_sim_b_propagates(self):
        with patch.object(portfolio, "run_simulation",
                          side_effect=lambda n: _sim(10, 8, 100, 110) if n == "A" else {"error": "boom"}):
            result = portfolio.compare_portfolios("A", "B")
        assert result["error"] == "boom"

    def test_backtest_error_returns_error(self):
        bad = _sim(10, 8, 100, 110)
        bad["backtest"]["error"] = "no data"
        with patch.object(portfolio, "run_simulation",
                          side_effect=lambda n: bad if n == "A" else _sim(10, 8, 100, 110)):
            result = portfolio.compare_portfolios("A", "B")
        assert result["error"] is not None


class TestCompareePortfoliosWinner:
    def _run(self, sim_a, sim_b):
        with patch.object(portfolio, "run_simulation",
                          side_effect=lambda n: sim_a if n == "A" else sim_b), \
             patch.object(portfolio, "load_portfolio", return_value={"holdings": {}}), \
             patch.object(portfolio, "_weak_link_score", return_value=100.0):
            return portfolio.compare_portfolios("A", "B")

    def test_higher_cagr_wins(self):
        sim_a = _sim(cagr=20, spy_cagr=8, final_value=150, p50_last=160)
        sim_b = _sim(cagr=5,  spy_cagr=8, final_value=100, p50_last=105)
        result = self._run(sim_a, sim_b)
        assert result["winner"] == "A"
        assert "Higher CAGR" in result["reasons"]
        assert result["score_a"] > result["score_b"]

    def test_lower_score_portfolio_b_wins(self):
        sim_a = _sim(cagr=2, spy_cagr=8, final_value=80, p50_last=85)
        sim_b = _sim(cagr=18, spy_cagr=8, final_value=140, p50_last=150)
        result = self._run(sim_a, sim_b)
        assert result["winner"] == "B"
        assert "Higher CAGR" in result["reasons"]

    def test_near_identical_scores_no_winner(self):
        sim_a = _sim(cagr=10, spy_cagr=8, final_value=100, p50_last=110)
        sim_b = _sim(cagr=10, spy_cagr=8, final_value=100, p50_last=110)
        result = self._run(sim_a, sim_b)
        assert result["winner"] is None
        assert result["reasons"] == ["Both portfolios perform similarly."]

    def test_result_includes_simulation_payloads(self):
        sim_a = _sim(cagr=10, spy_cagr=8, final_value=100, p50_last=110)
        sim_b = _sim(cagr=5,  spy_cagr=8, final_value=90,  p50_last=95)
        result = self._run(sim_a, sim_b)
        assert result["portfolio_a"] == sim_a
        assert result["portfolio_b"] == sim_b


class TestWeakLinkScore:
    def test_no_weak_links_gives_100(self):
        wl = {"error": None, "holdings": {
            "AAA": {"verdict": "contributor"},
            "BBB": {"verdict": "neutral"},
        }}
        with patch.object(portfolio, "analyze_weak_links", return_value=wl):
            score = portfolio._weak_link_score({"holdings": {}}, {})
        assert score == 100.0

    def test_some_weak_links_reduces_score(self):
        wl = {"error": None, "holdings": {
            "AAA": {"verdict": "weak link"},
            "BBB": {"verdict": "neutral"},
        }}
        with patch.object(portfolio, "analyze_weak_links", return_value=wl):
            score = portfolio._weak_link_score({"holdings": {}}, {})
        assert score == 50.0

    def test_error_gives_neutral_50(self):
        with patch.object(portfolio, "analyze_weak_links", return_value={"error": "x"}):
            score = portfolio._weak_link_score({"holdings": {}}, {})
        assert score == 50.0

