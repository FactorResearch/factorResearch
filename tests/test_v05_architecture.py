import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes import portfolio
from codes.engine import backtest, factor_backtest
from codes.core.engine_contracts import (
    EngineContract,
    EngineSchema,
    FeatureFlag,
    SchemaField,
    assert_feature_enabled,
    contract_to_dict,
    validate_engine_input,
    validate_engine_output,
)
from codes.core import financial_math as fm
from codes.core import model_utils as mu
from codes.data.providers import (
    CanonicalCompany,
    CanonicalFinancials,
    CanonicalFiscalPeriod,
    MarketProviderAdapter,
)
from codes.models import risk_metrics
from codes.models import (
    alternative_data,
    altman,
    bias_engine,
    buffett,
    capital_allocation,
    earnings_revision,
    fcf_quality,
    factor_momentum,
    graham,
    greenblatt,
    growth_quality,
    insider_activity,
    momentum,
    piotroski,
    profitability,
    quality,
    regime,
    spy_benchmark_model,
)
from codes.engine import market_fear


def test_shared_math_covers_v05_required_metrics():
    prices = [100, 105, 103, 112, 120]
    benchmark = [100, 102, 104, 108, 110]
    returns = fm.simple_returns(prices)
    benchmark_returns = fm.simple_returns(benchmark)

    assert fm.cagr(100, 121, 2) == pytest.approx(0.10)
    assert fm.volatility(returns) is not None
    assert fm.sharpe_ratio(returns, risk_free_rate=0.045) is not None
    assert fm.sortino_ratio([0.04, -0.02, 0.03], annual_return=0.12, risk_free_rate=0.045) is not None
    assert fm.max_drawdown(prices) == pytest.approx(-0.019047619, rel=1e-6)
    assert fm.calmar_ratio(0.12, -0.20) == pytest.approx(0.6)
    assert fm.covariance(returns, benchmark_returns) is not None
    assert fm.covariance_matrix([[0.01, 0.02], [0.02, 0.01], [0.03, 0.02]]) is not None
    assert fm.correlation(returns, benchmark_returns) is not None
    assert fm.correlation_matrix([[0.01, 0.02], [0.02, 0.01], [0.03, 0.02]]) is not None
    assert fm.beta(returns, benchmark_returns) is not None
    assert fm.alpha(0.12, 0.09, 1.1, risk_free_rate=0.045) == pytest.approx(0.0255)

    regression = fm.linear_regression([1, 2, 3], [2, 4, 6])
    assert regression["slope"] == pytest.approx(2.0)
    assert regression["r_squared"] == pytest.approx(1.0)
    assert fm.percentile_normalize(15, 10, 20) == pytest.approx(50.0)
    assert fm.percentile([1, 2, 3], 50) == pytest.approx(2.0)
    assert fm.percentile_rank([1, 2, 3], 2) == pytest.approx(66.6666667)
    assert fm.winsorize([1, 2, 100], lower_pct=0, upper_pct=50) == [1.0, 2.0, 2.0]
    assert fm.rank_values([10, 30, 30, None, 20]) == [4, 1, 1, None, 3]


def test_shared_model_utils_cover_repeated_model_helpers():
    records = [{"year": "2025", "value": "10.5"}, {"year": "2024", "value": None}]
    assert mu.safe_float("12.3") == pytest.approx(12.3)
    assert mu.safe_float(float("nan")) is None
    assert mu.clamp(150, 0, 100) == 100
    assert mu.first_record_value(records) == pytest.approx(10.5)
    assert mu.record_values(records) == [10.5]
    assert mu.records_by_year(records) == {2025: 10.5}
    assert mu.percent_change(100, 125) == pytest.approx(25.0)
    assert mu.linear_slope_percent([100, 110, 120]) is not None
    assert mu.score_from_criteria([{"score": 5, "max": 10}, {"score": 2, "max": 5}]) == (7.0, 15.0)


def _sample_contract():
    return EngineContract(
        name="sample_engine",
        version="0.5.0",
        feature_flags=frozenset({FeatureFlag.INTERNAL, FeatureFlag.BETA}),
        input_schema=EngineSchema((
            SchemaField("symbol", (str,), description="Ticker symbol"),
            SchemaField("price", (int, float), description="Current price"),
        )),
        output_schema=EngineSchema((
            SchemaField("total_score", (int, float), description="0-100 score"),
            SchemaField("signal", (str,), description="Legal-safe label"),
            SchemaField("notes", (list,), required=False, nullable=True),
        )),
        documentation="Sample engine contract for v0.5 tests.",
        interpretation_guide="Scores are diagnostics, not trading instructions.",
    )


def test_engine_contract_validates_schemas_and_feature_flags():
    contract = _sample_contract()

    assert validate_engine_input(contract, {"symbol": "AAPL", "price": 190.0}) == []
    issues = validate_engine_input(contract, {"symbol": "AAPL", "price": None})
    assert [(issue.field, issue.message) for issue in issues] == [("price", "field may not be null")]

    output_issues = validate_engine_output(contract, {"total_score": 80, "signal": "FAVORABLE"})
    assert output_issues == []

    assert contract.supports("internal") is True
    assert_feature_enabled(contract, FeatureFlag.BETA)
    with pytest.raises(PermissionError):
        assert_feature_enabled(contract, FeatureFlag.ENTERPRISE)


def test_engine_contract_serializes_for_docs_and_api_discovery():
    metadata = contract_to_dict(_sample_contract())
    assert metadata["name"] == "sample_engine"
    assert metadata["version"] == "0.5.0"
    assert metadata["feature_flags"] == ["beta", "internal"]
    assert metadata["input_schema"][0]["name"] == "symbol"
    assert "not trading instructions" in metadata["interpretation_guide"]


def test_provider_protocol_uses_canonical_models():
    class FakeProvider:
        provider_name = "fake"

        def get_company(self, symbol: str) -> CanonicalCompany:
            return CanonicalCompany(symbol=symbol, name="Example Inc.", currency="USD")

        def get_financials(self, symbol: str) -> CanonicalFinancials:
            company = self.get_company(symbol)
            period = CanonicalFiscalPeriod(2025, "FY", "2025-12-31", "USD")
            return CanonicalFinancials(company=company, periods=(period,))

        def get_filings(self, symbol: str) -> list[dict]:
            return []

        def get_shares(self, symbol: str) -> dict:
            return {"shares_outstanding": 1000}

        def get_currency(self, symbol: str) -> str | None:
            return "USD"

        def get_listing_information(self, symbol: str) -> dict:
            return {"exchange": "NYSE"}

    provider: MarketProviderAdapter = FakeProvider()
    financials = provider.get_financials("TEST")
    assert financials.company.symbol == "TEST"
    assert financials.periods[0].fiscal_year == 2025
    assert provider.get_currency("TEST") == "USD"


def test_risk_metrics_exposes_v05_engine_contract():
    contract = risk_metrics.get_contract()
    assert contract.name == "risk_metrics"
    assert contract.supports(FeatureFlag.V1)
    assert contract.interpretation_guide

    issues = risk_metrics.validate_input({"price_hist": "not-a-frame"})
    assert issues[0].field == "price_hist"

    output = risk_metrics.score(
        pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=6, freq="MS"),
            "Close": [100, 101, 103, 102, 106, 108],
        })
    )
    assert risk_metrics.validate_output(output) == []


def test_existing_calculation_modules_are_wired_to_shared_math():
    modules = [
        portfolio,
        backtest,
        factor_backtest,
        buffett,
        fcf_quality,
        growth_quality,
        momentum,
        regime,
        risk_metrics,
        spy_benchmark_model,
    ]
    for module in modules:
        assert getattr(module, "fm") is fm


def test_existing_models_are_wired_to_shared_model_utils():
    modules = [
        alternative_data,
        altman,
        bias_engine,
        buffett,
        capital_allocation,
        earnings_revision,
        fcf_quality,
        factor_momentum,
        graham,
        greenblatt,
        growth_quality,
        insider_activity,
        market_fear,
        piotroski,
        profitability,
        quality,
        regime,
    ]
    for module in modules:
        assert getattr(module, "mu") is mu
