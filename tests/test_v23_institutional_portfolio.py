import pandas as pd

from codes import portfolio
from codes.engine import institutional_portfolio
from codes.services.permissions import Feature, PermissionResult


def _history(start, step, periods=36):
    dates = pd.date_range("2022-01-31", periods=periods, freq="ME")
    close = [start + step * index for index in range(periods)]
    return pd.DataFrame({"Date": dates, "Close": close})


def _portfolio():
    return {
        "name": "Institutional",
        "holdings": {
            "AAA": {"shares": 10, "price_at_add": 100, "current_price": 120},
            "BBB": {"shares": 5, "price_at_add": 200, "current_price": 180},
            "CCC": {"shares": 8, "price_at_add": 50, "current_price": 70},
        },
    }


def _analyses():
    return {
        "AAA": {
            "sector": "Technology",
            "industry": "Software",
            "country": "United States",
            "market_cap": 250_000,
            "enhanced": {"quality_pct": 80, "momentum_pct": 40, "graham_pct": 45, "risk_pct": 60},
        },
        "BBB": {
            "sector": "Technology",
            "industry": "Semiconductors",
            "country": "United States",
            "market_cap": 50_000,
            "enhanced": {"quality_pct": 55, "momentum_pct": 72, "graham_pct": 40, "risk_pct": 50},
        },
        "CCC": {
            "sector": "Health Care",
            "industry": "Medical Devices",
            "country": "Canada",
            "market_cap": 3_000,
            "enhanced": {"quality_pct": 48, "momentum_pct": 42, "graham_pct": 68, "risk_pct": 46},
        },
    }


def test_institutional_portfolio_calculates_v23_surface_area():
    result = institutional_portfolio.analyze_portfolio(
        _portfolio(),
        analyses=_analyses(),
        histories={
            "AAA": _history(100, 2),
            "BBB": _history(200, 1),
            "CCC": _history(50, 1.5),
        },
        benchmark_symbol="QQQ",
        benchmark_history=_history(300, 2),
    )

    assert result["engine_version"] == "2.3.0"
    assert result["benchmark"]["selected"] == "QQQ"
    assert result["exposures"]["sector"]["Technology"] > 70
    assert "United States" in result["exposures"]["country"]
    assert "Mega" in result["exposures"]["market_cap"]
    assert result["estimated_liquidity"]["score"] > 0
    assert result["correlation_matrix"]["symbols"] == ["AAA", "BBB", "CCC"]
    assert result["hierarchical_clustering"]["clusters"]
    assert result["pca"]["components"]
    assert result["historical_stress_testing"]
    assert set(result["advanced_monte_carlo"]) == {"gbm", "bootstrap", "fat_tail", "regime_aware"}
    assert result["advanced_monte_carlo"]["gbm"]["series"]["months"][0] == 0
    assert len(result["advanced_monte_carlo"]["gbm"]["series"]["p50"]) == 25
    assert result["risk_budget"]["holdings"]
    assert result["scenario_shocks"]
    assert result["policy_checks"]["checks"]
    assert result["portfolio_factor_exposure"]["quality"]["score"] is not None
    assert result["attribution"]["holdings"]
    assert result["rolling_attribution"]
    assert "recommendations" in result["rebalancing_optimizer"]
    assert "estimated_annual_income" in result["income_yield"]
    assert "tax_loss_candidates" in result["tax_view"]


def test_institutional_wrapper_does_not_write_json_cache(monkeypatch):
    writes = []
    monkeypatch.setattr(portfolio.db, "get_analysis", lambda symbol: _analyses().get(symbol))
    monkeypatch.setattr(portfolio, "_load_history", lambda symbol: _history(100, 1))
    monkeypatch.setattr(portfolio.cache, "write", lambda *args, **kwargs: writes.append(args))

    result = portfolio.run_institutional_analytics(_portfolio())

    assert result["error"] is None
    assert result["advanced_monte_carlo"]["gbm"]["tier"] == "advanced"
    assert writes == []


def test_advanced_monte_carlo_chart_renders_all_methods():
    from codes.app_modules.tabs import portfolio as portfolio_tab

    analytics = institutional_portfolio.analyze_portfolio(
        _portfolio(),
        analyses=_analyses(),
        histories={
            "AAA": _history(100, 2),
            "BBB": _history(200, 1),
            "CCC": _history(50, 1.5),
        },
    )

    monte_carlo = {
        "error": None,
        "spy_p10": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88,
                    87, 86, 85, 84, 83, 82, 81, 80, 79, 78, 77, 76],
        "spy_p50": [100 + index for index in range(25)],
        "spy_p90": [100 + index * 2 for index in range(25)],
    }

    chart = portfolio_tab._advanced_monte_carlo_chart(analytics, "Institutional", monte_carlo)
    text = str(chart)
    trace_names = {trace.name for trace in chart.children[1].figure.data}

    assert "Pro Monte Carlo" in text
    assert "SPY projected median" in trace_names
    assert "SPY projected range" in trace_names
    assert "GBM median" in text
    assert "Bootstrap median" in text
    assert "Fat-tail median" in text
    assert "Regime-aware median" in text


def test_monte_carlo_plan_flag_separates_basic_and_pro():
    from codes.app_modules.tabs import portfolio as portfolio_tab

    basic = PermissionResult(True, Feature.PORTFOLIO_ANALYTICS, plan="free", status="trialing")
    pro = PermissionResult(True, Feature.PORTFOLIO_ANALYTICS, plan="premium", status="active")
    internal = PermissionResult(True, Feature.PORTFOLIO_ANALYTICS, plan="premium", status="internal")

    assert portfolio_tab._use_pro_monte_carlo(basic) is False
    assert portfolio_tab._use_pro_monte_carlo(pro) is True
    assert portfolio_tab._use_pro_monte_carlo(internal) is True
