import pandas as pd

from codes.app_modules import analysis


def test_calculate_factor_research_from_stock_and_spy_history():
    dates = pd.date_range("2024-01-01", periods=18, freq="MS")
    spy_close = [100 * (1.01 ** index) for index in range(18)]
    stock_close = [50 * (1.012 ** index) for index in range(18)]
    hist = pd.DataFrame({"Date": dates, "Close": stock_close})
    spy_hist = pd.DataFrame({"Date": dates, "Close": spy_close})

    result = analysis._calculate_factor_research(hist, spy_hist)

    assert result["status"] == "ready"
    assert result["model"] == "capm"
    assert result["capm"]["observations"] == 17
    assert "mkt_rf" in result["capm"]["betas"]
    assert "ff3" in result["pending_models"]


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
    assert "CAPM vs SPY" in str(card)
