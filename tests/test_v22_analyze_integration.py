import pandas as pd

from codes.app_modules import analysis


def test_calculate_factor_research_from_stock_and_spy_history():
    dates = pd.date_range("2024-01-01", periods=30, freq="MS")
    stock_close = [50 * (1.012 ** index) for index in range(30)]
    hist = pd.DataFrame({"Date": dates, "Close": stock_close})
    factor_frame = pd.DataFrame({
        "Date": dates.strftime("%Y-%m-%d"),
        "mkt_rf": [0.01] * 30,
        "smb": [0.002] * 30,
        "hml": [0.001] * 30,
        "rmw": [0.003] * 30,
        "cma": [0.0015] * 30,
        "mom": [0.004] * 30,
        "rf": [0.0002] * 30,
    })

    original = analysis.factor_returns.get_us_monthly_factors
    analysis.factor_returns.get_us_monthly_factors = lambda: factor_frame
    try:
        result = analysis._calculate_factor_research(hist)
    finally:
        analysis.factor_returns.get_us_monthly_factors = original

    assert result["status"] == "ready"
    assert set(result["models"]) == {"capm", "ff3", "ff5", "carhart4"}
    assert result["ff5"]["factors"] == ["mkt_rf", "smb", "hml", "rmw", "cma"]
    assert result["return_attribution"]["total_excess_return"] is not None
    assert result["rolling_attribution"]


def test_legacy_cached_analysis_backfills_factor_research_card():
    from codes.app_modules import analysis_ui

    dates = pd.date_range("2024-01-01", periods=18, freq="MS")
    data = {
        "price_history": {
            "Date": {index: str(date.date()) for index, date in enumerate(dates)},
            "Close": {index: 50 * (1.012 ** index) for index in range(18)},
        },
        "spy_history": {
            "Date": {index: str(date.date()) for index, date in enumerate(dates)},
            "Close": {index: 100 * (1.01 ** index) for index in range(18)},
        },
    }

    card = analysis_ui._factor_research_card(data)

    assert "Factor Research" in str(card)
    assert "CAPM" in str(card)
