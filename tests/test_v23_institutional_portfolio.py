import pandas as pd

from codes import portfolio
from codes.engine import institutional_portfolio


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
    )

    assert result["engine_version"] == "2.3.0"
    assert result["exposures"]["sector"]["Technology"] > 70
    assert "United States" in result["exposures"]["country"]
    assert "Mega" in result["exposures"]["market_cap"]
    assert result["estimated_liquidity"]["score"] > 0
    assert result["correlation_matrix"]["symbols"] == ["AAA", "BBB", "CCC"]
    assert result["hierarchical_clustering"]["clusters"]
    assert result["pca"]["components"]
    assert result["historical_stress_testing"]
    assert set(result["advanced_monte_carlo"]) == {"gbm", "bootstrap", "fat_tail", "regime_aware"}


def test_institutional_wrapper_does_not_write_json_cache(monkeypatch):
    writes = []
    monkeypatch.setattr(portfolio.db, "get_analysis", lambda symbol: _analyses().get(symbol))
    monkeypatch.setattr(portfolio, "_load_history", lambda symbol: _history(100, 1))
    monkeypatch.setattr(portfolio.cache, "write", lambda *args, **kwargs: writes.append(args))

    result = portfolio.run_institutional_analytics(_portfolio())

    assert result["error"] is None
    assert result["advanced_monte_carlo"]["gbm"]["tier"] == "advanced"
    assert writes == []
