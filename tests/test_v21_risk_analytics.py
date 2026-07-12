import os
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.models import distress_scores, portfolio_risk_analytics
from codes.app_modules import analysis, analysis_ui
from codes import portfolio


def _rec(value):
    return [{"value": value}]


def _sec(**overrides):
    base = {
        "total_assets": _rec(1_000_000),
        "tot_lib": _rec(450_000),
        "cur_ast": _rec(300_000),
        "cur_lib": _rec(150_000),
        "net_inc": [{"value": 80_000}, {"value": 70_000}],
        "op_cf": _rec(110_000),
        "retained_earnings": _rec(300_000),
        "op_income": _rec(120_000),
        "shares": _rec(10_000),
        "revenue": _rec(900_000),
        "ppe_net": _rec(100_000),
    }
    base.update(overrides)
    return base


def test_portfolio_risk_analytics_computes_drawdown_and_tail_risk():
    dates = pd.date_range("2020-01-31", periods=18, freq="ME").strftime("%Y-%m-%d").tolist()
    values = [
        100, 110, 120, 90, 80, 100, 125, 130, 120,
        140, 150, 145, 160, 155, 170, 165, 180, 190,
    ]

    result = portfolio_risk_analytics.analyze_equity_curve(dates, values)

    assert result["error"] is None
    assert result["max_drawdown"] == pytest.approx(-33.33, abs=0.01)
    assert result["recovery_time_months"] == 2
    assert result["var_95"] < 0
    assert result["cvar_95"] <= result["var_95"]
    assert result["ulcer_index"] > 0
    assert result["worst_month"]["return"] == pytest.approx(-25.0)
    assert result["drawdown_curve"][0]["drawdown"] == 0
    assert result["rolling_sharpe"]
    assert result["rolling_sortino"]


def test_portfolio_run_simulation_includes_v21_risk_analytics():
    backtest = {
        "error": None,
        "dates": pd.date_range("2021-01-31", periods=14, freq="ME").strftime("%Y-%m-%d").tolist(),
        "portfolio_value": [100, 105, 95, 90, 110, 120, 118, 130, 128, 140, 135, 150, 145, 160],
    }

    with patch.object(portfolio, "load_portfolio", return_value={"holdings": {"AAPL": {"shares": 10}}}), \
         patch.object(portfolio.cache, "read", return_value=None), \
         patch.object(portfolio, "_write_cache_or_raise", return_value=None), \
         patch.object(portfolio, "run_backtest", return_value=backtest), \
         patch.object(portfolio, "run_montecarlo", return_value={"error": None}):
        result = portfolio.run_simulation("u1", "Risk")

    assert result["risk_analytics"]["error"] is None
    assert result["risk_analytics"]["max_drawdown"] < 0
    assert "rolling_sharpe" in result["risk_analytics"]


def test_cached_portfolio_simulation_backfills_v21_risk_analytics():
    cached = {
        "portfolio_name": "Cached",
        "backtest": {
            "error": None,
            "dates": pd.date_range("2021-01-31", periods=14, freq="ME").strftime("%Y-%m-%d").tolist(),
            "portfolio_value": [100, 105, 95, 90, 110, 120, 118, 130, 128, 140, 135, 150, 145, 160],
        },
        "montecarlo": {"error": None},
        "holdings": {},
    }

    with patch.object(portfolio, "load_portfolio", return_value={"holdings": {"AAPL": {"shares": 10}}}), \
         patch.object(portfolio.cache, "read", return_value=cached):
        result = portfolio.run_simulation("u1", "Cached")

    assert result["risk_analytics"]["error"] is None
    assert result["risk_analytics"]["max_drawdown"] < 0


def test_distress_scores_include_ohlson_zmijewski_and_altman():
    result = distress_scores.score(25.0, _sec())

    assert result["ohlson"]["error"] is None
    assert result["zmijewski"]["error"] is None
    assert result["altman"]["zone"] in {"safe", "grey", "distress", "unknown"}
    assert result["consensus"]["zone"] in {"low", "elevated", "high", "unknown"}
    assert 0 <= result["ohlson"]["probability"] <= 100
    assert 0 <= result["zmijewski"]["probability"] <= 100


def test_distress_scores_return_unknown_when_required_inputs_missing():
    result = distress_scores.score(None, _sec(total_assets=[]))

    assert result["ohlson"]["zone"] == "unknown"
    assert result["zmijewski"]["zone"] == "unknown"
    assert result["consensus"]["zone"] in {"low", "elevated", "high", "unknown"}


def test_analyze_tab_renders_v21_distress_score_cards():
    payload = {
        "distress_scores": {
            "ohlson": {
                "o_score": -2.1,
                "probability": 12.3,
                "zone": "low",
                "note": "Ohlson low",
                "components": {
                    "size_log_assets_millions": 1.2,
                    "total_liabilities_to_assets": 0.3,
                },
            },
            "zmijewski": {
                "x_score": -3.2,
                "probability": 18.4,
                "zone": "low",
                "note": "Zmijewski low",
                "components": {
                    "return_on_assets": 0.08,
                    "liabilities_to_assets": 0.4,
                    "current_ratio": 2.0,
                },
            },
            "altman": {"zone": "safe"},
            "consensus": {"zone": "low", "models_available": 3, "note": "Consensus low"},
        }
    }
    ohlson = analysis_ui._ohlson_card(payload)
    zmijewski = analysis_ui._zmijewski_card(payload)

    assert ohlson.className == "scorecard"
    assert zmijewski.className == "scorecard"
    assert "Ohlson O-Score" in str(ohlson)
    assert "Size" in str(ohlson)
    assert "Zmijewski Score" in str(zmijewski)
    assert "Current Ratio" in str(zmijewski)


def test_cached_analysis_payload_backfills_v21_distress_scores(monkeypatch):
    payload = {
        "symbol": "TEST",
        "price": 25.0,
        "altman": {"zone": "safe", "z_score": 3.0, "risk_score": 75},
    }
    monkeypatch.setattr(analysis.sec_data, "get_financials", lambda symbol: _sec())

    result = analysis._attach_v21_distress_scores(payload)

    assert result["distress_scores"]["ohlson"]["error"] is None
    assert result["distress_scores"]["zmijewski"]["error"] is None
