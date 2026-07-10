from unittest.mock import Mock

from codes.app_modules.rate_limit import RateLimited
from codes.app_modules.tabs import portfolio
from codes.services.permissions import Feature, PermissionResult


def test_paid_user_can_run_simulation_and_usage_is_recorded(monkeypatch):
    monkeypatch.setattr(portfolio, "get_user_id", lambda: "paid-user")
    allow = PermissionResult(True, Feature.BACKTEST, plan="premium", status="active")
    monkeypatch.setattr(portfolio.permissions, "can_access_feature", lambda *_: allow)
    limiter = Mock()
    monkeypatch.setattr(portfolio, "check_rate_limit", limiter)
    comparison = {"error": None}
    monkeypatch.setattr(portfolio.portfolio_engine, "compare_portfolios", lambda *_: comparison)
    monkeypatch.setattr(portfolio, "_build_comparison_view", lambda *_: ["charts"])
    usage = Mock()
    monkeypatch.setattr(portfolio.permissions, "record_feature_usage", usage)

    assert portfolio.run_simulation(1, "Growth", "Income") == ["charts"]
    limiter.assert_called_once_with(
        "portfolio_simulation", calls=3, period_seconds=3600, key="paid-user"
    )
    usage.assert_called_once_with(
        "paid-user", Feature.BACKTEST, usage_key="portfolio:Growth:Income"
    )


def test_rate_limited_user_does_not_run_simulation(monkeypatch):
    monkeypatch.setattr(portfolio, "get_user_id", lambda: "paid-user")
    allow = PermissionResult(True, Feature.BACKTEST, plan="premium", status="active")
    monkeypatch.setattr(portfolio.permissions, "can_access_feature", lambda *_: allow)
    monkeypatch.setattr(
        portfolio, "check_rate_limit", Mock(side_effect=RateLimited(retry_after=42))
    )
    simulation = Mock()
    monkeypatch.setattr(portfolio.portfolio_engine, "run_simulation", simulation)

    result = portfolio.run_simulation(1, "Growth", None)

    assert "rate limit" in result.children.lower()
    assert "42 seconds" in result.children
    simulation.assert_not_called()


def test_trial_user_is_blocked_before_rate_limit_or_simulation(monkeypatch):
    monkeypatch.setattr(portfolio, "get_user_id", lambda: "trial-user")
    deny = PermissionResult(
        False,
        Feature.BACKTEST,
        reason="Historical backtesting requires Premium.",
        upgrade_required=True,
    )
    monkeypatch.setattr(portfolio.permissions, "can_access_feature", lambda *_: deny)
    limiter = Mock()
    simulation = Mock()
    monkeypatch.setattr(portfolio, "check_rate_limit", limiter)
    monkeypatch.setattr(portfolio.portfolio_engine, "run_simulation", simulation)

    result = portfolio.run_simulation(1, "Growth", None)

    assert "requires Premium" in result.children
    assert "Upgrade" in result.children
    limiter.assert_not_called()
    simulation.assert_not_called()
