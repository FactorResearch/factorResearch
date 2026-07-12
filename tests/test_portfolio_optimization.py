import numpy as np
import pandas as pd
import pytest
import sys
import os

pytest.importorskip("scipy")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.models.portfolio_optimization import optimize_portfolio
from codes import portfolio


def _returns_frame():
    rng = np.random.default_rng(7)
    base = rng.normal(0.008, 0.035, 72)
    return pd.DataFrame({
        "AAA": base,
        "BBB": base * 0.35 + rng.normal(0.004, 0.018, 72),
        "CCC": rng.normal(0.003, 0.012, 72),
    })


def _variance(weights, returns):
    cov = returns.cov().values * 12
    arr = np.array([weights[symbol] for symbol in returns.columns])
    return float(arr @ cov @ arr)


def test_optimizers_return_long_only_fully_invested_weights():
    returns = _returns_frame()

    result = optimize_portfolio(
        returns,
        {"AAA": 0.5, "BBB": 0.3, "CCC": 0.2},
        risk_free_rate=0.02,
    )

    assert result["error"] is None
    assert result["symbols"] == ["AAA", "BBB", "CCC"]
    assert set(result["methods"]) == {
        "current",
        "mean_variance",
        "max_sharpe",
        "min_variance",
        "risk_parity",
    }
    for method in result["methods"].values():
        weights = method["weights"]
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-5)
        assert all(0.0 <= weight <= 1.0 for weight in weights.values())
        assert method["volatility"] >= 0


def test_min_variance_reduces_variance_against_current_allocation():
    returns = _returns_frame()

    result = optimize_portfolio(
        returns,
        {"AAA": 0.8, "BBB": 0.1, "CCC": 0.1},
        risk_free_rate=0.02,
    )

    current_var = _variance(result["methods"]["current"]["weights"], returns)
    min_var = _variance(result["methods"]["min_variance"]["weights"], returns)
    assert min_var <= current_var


def test_risk_parity_balances_risk_contributions():
    returns = _returns_frame()

    result = optimize_portfolio(
        returns,
        {"AAA": 0.6, "BBB": 0.3, "CCC": 0.1},
        risk_free_rate=0.02,
    )

    contributions = result["methods"]["risk_parity"]["risk_contribution"]
    assert sum(contributions.values()) == pytest.approx(1.0, abs=1e-5)
    assert max(contributions.values()) - min(contributions.values()) < 0.15


def test_portfolio_wrapper_uses_aligned_price_history(monkeypatch):
    dates = pd.date_range("2019-01-31", periods=48, freq="ME")
    prices = {
        "AAA": pd.DataFrame({"Date": dates, "Close": np.linspace(100, 160, len(dates))}),
        "BBB": pd.DataFrame({"Date": dates, "Close": np.linspace(80, 100, len(dates))}),
    }

    monkeypatch.setattr(portfolio, "load_portfolio", lambda user_id, name: {
        "name": name,
        "holdings": {
            "AAA": {"shares": 10, "price_at_add": 100},
            "BBB": {"shares": 20, "price_at_add": 80},
        },
    })
    monkeypatch.setattr(portfolio, "_load_history", lambda symbol: prices[symbol])

    result = portfolio.optimize_portfolio("user-1", "Test")

    assert result["error"] is None
    assert result["portfolio_name"] == "Test"
    assert result["symbols"] == ["AAA", "BBB"]
    assert result["methods"]["current"]["weights"]["AAA"] == pytest.approx(1000 / 2600, abs=1e-5)
    assert result["methods"]["current"]["weights"]["BBB"] == pytest.approx(1600 / 2600, abs=1e-5)


def test_portfolio_wrapper_returns_clear_error_for_empty_portfolio(monkeypatch):
    monkeypatch.setattr(portfolio, "load_portfolio", lambda user_id, name: {
        "name": name,
        "holdings": {},
    })

    result = portfolio.optimize_portfolio("user-1", "Empty")

    assert result["error"] == "Portfolio is empty"
