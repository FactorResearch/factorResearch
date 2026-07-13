import pandas as pd
import pytest

from codes.core.engine_contracts import FeatureFlag
from codes.engine import factor_research


def _factor_frame(periods=48):
    rows = []
    for index in range(periods):
        mkt = -0.02 + (index % 7) * 0.01
        smb = -0.01 + (index % 5) * 0.005
        hml = 0.008 - (index % 4) * 0.004
        mom = -0.006 + (index % 6) * 0.003
        rmw = 0.004 + (index % 3) * 0.002
        cma = -0.003 + (index % 4) * 0.001
        asset = 0.001 + 1.2 * mkt + 0.4 * smb - 0.25 * hml + 0.15 * mom
        rows.append({
            "Date": pd.Timestamp("2022-01-01") + pd.DateOffset(months=index),
            "asset_return": asset,
            "mkt_rf": mkt,
            "smb": smb,
            "hml": hml,
            "mom": mom,
            "rmw": rmw,
            "cma": cma,
        })
    return pd.DataFrame(rows)


def test_factor_research_contract_supports_v2():
    contract = factor_research.get_contract()

    assert contract.name == "factor_research"
    assert contract.version == "2.2.0"
    assert contract.supports(FeatureFlag.V2)
    assert factor_research.validate_input({"returns": _factor_frame(), "model": "ff3"}) == []


def test_capm_recovers_market_beta_and_alpha():
    frame = _factor_frame()
    frame["asset_return"] = 0.001 + 1.2 * frame["mkt_rf"]

    result = factor_research.capm(frame)

    assert result["model"] == "capm"
    assert result["observations"] == len(frame)
    assert result["betas"]["mkt_rf"] == pytest.approx(1.2, abs=0.06)
    assert result["alpha_annualized"] == pytest.approx(0.012, abs=0.003)
    assert result["return_attribution"]["factor_contributions"]["mkt_rf"] is not None


def test_fama_french_and_carhart_models_expose_expected_factors():
    frame = _factor_frame()

    ff3 = factor_research.fama_french_3(frame)
    carhart = factor_research.carhart_4(frame)
    ff5 = factor_research.fama_french_5(frame)

    assert ff3["factors"] == ["mkt_rf", "smb", "hml"]
    assert set(carhart["factors"]) == {"mkt_rf", "smb", "hml", "mom"}
    assert set(ff5["factors"]) == {"mkt_rf", "smb", "hml", "rmw", "cma"}
    assert carhart["betas"]["mkt_rf"] == pytest.approx(1.2, abs=0.001)
    assert carhart["betas"]["smb"] == pytest.approx(0.4, abs=0.001)
    assert carhart["betas"]["hml"] == pytest.approx(-0.25, abs=0.001)
    assert carhart["betas"]["mom"] == pytest.approx(0.15, abs=0.001)


def test_holdings_attribution_weights_factor_exposures():
    holdings = {
        "AAPL": {"shares": 10, "price": 200},
        "MSFT": {"shares": 5, "price": 100},
    }
    holding_results = {
        "AAPL": {
            "betas": {"mkt_rf": 1.2, "smb": 0.2},
            "return_attribution": {"factor_contributions": {"mkt_rf": 0.06, "smb": 0.01}},
        },
        "MSFT": {
            "betas": {"mkt_rf": 0.8, "smb": -0.1},
            "return_attribution": {"factor_contributions": {"mkt_rf": 0.03, "smb": -0.005}},
        },
    }

    result = factor_research.holdings_attribution(holdings, holding_results)

    assert result["weights"]["AAPL"] == pytest.approx(0.8)
    assert result["weights"]["MSFT"] == pytest.approx(0.2)
    assert result["portfolio_betas"]["mkt_rf"] == pytest.approx(1.12)
    assert result["portfolio_factor_contributions"]["smb"] == pytest.approx(0.007)


def test_rolling_attribution_returns_window_results():
    frame = _factor_frame(periods=18)

    rows = factor_research.rolling_attribution(frame, model="carhart4", window=12, min_periods=12)

    assert len(rows) == 7
    assert rows[0]["observations"] == 12
    assert "mkt_rf" in rows[-1]["betas"]
    assert rows[-1]["end_date"] == "2023-06-01"
