"""ISSUE_030 Phase 2 option-chain provider and cache tests."""

from datetime import datetime, timezone
import os
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.data import api_fetcher
from codes.app_modules import analysis as stock_analysis
from codes.data.options_chain import (
    FinnhubOptionsChainProvider,
    OptionsChainProviderError,
    normalize_finnhub_chain,
)


FETCHED_AT = datetime(2026, 7, 11, 14, 30, tzinfo=timezone.utc)


def _payload():
    return {
        "code": "AAPL",
        "exchange": "OPRA",
        "data": [
            {
                "expirationDate": "2026-08-21",
                "options": {
                    "CALL": [
                        {
                            "contractName": "AAPL260821C00200000",
                            "contractSize": "REGULAR",
                            "currency": "USD",
                            "type": "CALL",
                            "inTheMoney": False,
                            "strike": "200",
                            "lastPrice": "5.05",
                            "bid": "4.90",
                            "ask": "5.10",
                            "volume": 321,
                            "openInterest": 2450,
                            "impliedVolatility": "0.2845",
                            "delta": "0.52",
                            "gamma": "0.031",
                            "theta": "-0.08",
                            "vega": "0.12",
                            "rho": "0.04",
                            "theoretical": "5.02",
                            "intrinsicValue": "0",
                            "timeValue": "5.05",
                            "lastTradeDateTime": 1783719000,
                            "updatedAt": "2026-07-11T14:29:00Z",
                        }
                    ],
                    "PUT": [
                        {
                            "contractName": "AAPL260821P00200000",
                            "contractSize": "REGULAR",
                            "currency": "USD",
                            "type": "PUT",
                            "inTheMoney": True,
                            "strike": 200,
                            "lastPrice": 4.8,
                            "bid": 4.7,
                            "ask": 4.9,
                            "volume": 150,
                            "openInterest": 1800,
                            "impliedVolatility": 0.276,
                        }
                    ],
                },
            }
        ],
    }


def test_normalize_finnhub_chain_preserves_quote_liquidity_iv_and_metadata():
    snapshot = normalize_finnhub_chain(_payload(), "aapl", fetched_at=FETCHED_AT)
    result = snapshot.to_dict()

    assert result["symbol"] == "AAPL"
    assert result["provider"] == "FINNHUB"
    assert result["status"] == "AVAILABLE"
    assert result["exchange"] == "OPRA"
    assert result["contract_count"] == 2

    call = result["contracts"][0]
    assert call["contract_symbol"] == "AAPL260821C00200000"
    assert call["option_type"] == "CALL"
    assert call["expiration_date"] == "2026-08-21"
    assert call["days_to_expiry"] == 41
    assert call["strike"] == pytest.approx(200)
    assert call["bid"] == pytest.approx(4.9)
    assert call["ask"] == pytest.approx(5.1)
    assert call["mid"] == pytest.approx(5.0)
    assert call["spread_pct"] == pytest.approx(0.04)
    assert call["volume"] == 321
    assert call["open_interest"] == 2450
    assert call["implied_volatility"] == pytest.approx(0.2845)
    assert call["delta"] == pytest.approx(0.52)
    assert call["gamma"] == pytest.approx(0.031)
    assert call["theta"] == pytest.approx(-0.08)
    assert call["theoretical_value"] == pytest.approx(5.02)
    assert call["contract_multiplier"] == 100
    assert call["currency"] == "USD"
    assert call["in_the_money"] is False
    assert call["updated_at"] == "2026-07-11T14:29:00+00:00"


def test_normalizer_skips_malformed_contracts_without_poisoning_chain():
    payload = _payload()
    payload["data"][0]["options"]["CALL"].extend([
        {"contractName": "NO_STRIKE", "type": "CALL"},
        {"contractName": "BAD_TYPE", "type": "WARRANT", "strike": 100},
    ])
    snapshot = normalize_finnhub_chain(payload, "AAPL", fetched_at=FETCHED_AT)
    assert len(snapshot.contracts) == 2


def test_normalizer_returns_explicit_no_data_status_for_empty_chain():
    snapshot = normalize_finnhub_chain({"data": []}, "AAPL", fetched_at=FETCHED_AT)
    assert snapshot.status == "NO_DATA"
    assert snapshot.contracts == ()


def test_normalizer_rejects_provider_error_payload():
    with pytest.raises(OptionsChainProviderError, match="entitlement"):
        normalize_finnhub_chain({"error": "Missing options entitlement"}, "AAPL")


def test_finnhub_adapter_uses_keyword_symbol_and_rate_limit_hooks():
    events = []

    class Client:
        def option_chain(self, **params):
            events.append(("request", params))
            return _payload()

    provider = FinnhubOptionsChainProvider(
        Client(),
        before_request=lambda: events.append(("before", None)),
        after_request=lambda: events.append(("after", None)),
        clock=lambda: FETCHED_AT,
    )
    snapshot = provider.fetch_chain("aapl")

    assert snapshot.status == "AVAILABLE"
    assert events == [
        ("before", None),
        ("request", {"symbol": "AAPL"}),
        ("after", None),
    ]


def test_finnhub_adapter_wraps_client_errors_without_credentials_or_url():
    class Client:
        def option_chain(self, **params):
            raise RuntimeError("request URL containing secret token")

    provider = FinnhubOptionsChainProvider(Client(), clock=lambda: FETCHED_AT)
    with pytest.raises(OptionsChainProviderError) as exc_info:
        provider.fetch_chain("AAPL")
    assert "RuntimeError" in str(exc_info.value)
    assert "secret token" not in str(exc_info.value)


def test_api_fetcher_accepts_injected_provider_and_caches_normalized_result(monkeypatch):
    writes = []

    class Provider:
        name = "TEST_VENDOR"

        def fetch_chain(self, symbol):
            return normalize_finnhub_chain(_payload(), symbol, fetched_at=FETCHED_AT)

    monkeypatch.setattr(api_fetcher, "read_entry", lambda kind, key: None)
    monkeypatch.setattr(api_fetcher, "write", lambda kind, key, data: writes.append((kind, key, data)))

    result = api_fetcher.get_options_chain("aapl", provider=Provider())
    assert result["status"] == "AVAILABLE"
    assert result["contract_count"] == 2
    assert writes[0][0:2] == ("options_chain", "test_vendor-aapl")


def test_api_fetcher_returns_fresh_cache_without_calling_provider(monkeypatch):
    cached = {
        "symbol": "AAPL",
        "provider": "TEST_VENDOR",
        "status": "AVAILABLE",
        "contracts": [],
        "contract_count": 0,
    }

    class Provider:
        name = "TEST_VENDOR"

        def fetch_chain(self, symbol):
            raise AssertionError("fresh cache should bypass provider")

    monkeypatch.setattr(
        api_fetcher,
        "read_entry",
        lambda kind, key: {"ts": api_fetcher.time.time(), "data": cached},
    )
    assert api_fetcher.get_options_chain("AAPL", provider=Provider()) is cached


def test_api_fetcher_marks_old_cache_stale_when_provider_fails(monkeypatch):
    cached = {
        "symbol": "AAPL",
        "provider": "TEST_VENDOR",
        "status": "AVAILABLE",
        "contracts": [{"contract_symbol": "AAPL-C"}],
        "contract_count": 1,
    }

    class Provider:
        name = "TEST_VENDOR"

        def fetch_chain(self, symbol):
            raise OptionsChainProviderError("temporary failure")

    monkeypatch.setattr(
        api_fetcher,
        "read_entry",
        lambda kind, key: {"ts": 0, "data": cached},
    )
    result = api_fetcher.get_options_chain("AAPL", provider=Provider())
    assert result["status"] == "STALE"
    assert result["contract_count"] == 1
    assert "last chain snapshot" in result["error"]


def test_analysis_pipeline_passes_normalized_chain_to_options_engine(monkeypatch):
    """The live chain must survive the fetch/model boundary unchanged."""
    chain = normalize_finnhub_chain(_payload(), "AAPL", fetched_at=FETCHED_AT).to_dict()
    hist = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=12, freq="MS"),
        "Close": [100 + i for i in range(12)],
        "AdjClose": [100 + i for i in range(12)],
    })
    captured = {}

    monkeypatch.setattr(stock_analysis, "_analysis_cache", {})
    monkeypatch.setattr(stock_analysis.db, "get_analysis", lambda symbol: None)
    monkeypatch.setattr(stock_analysis.sec_data, "get_financials", lambda symbol: {
        "name": "Apple Inc.", "sector": "Technology", "shares": [{"value": 1_000_000}],
    })
    monkeypatch.setattr(stock_analysis.quality, "score", lambda facts: {})
    monkeypatch.setattr(stock_analysis.api_fetcher, "get_price", lambda symbol: 200.0)
    monkeypatch.setattr(stock_analysis.earnings_revision, "get_revision_score", lambda symbol: {})
    monkeypatch.setattr(stock_analysis.api_fetcher, "get_price_history", lambda symbol, years: hist)
    monkeypatch.setattr(stock_analysis, "_get_spy_history_lazy", lambda: hist)
    monkeypatch.setattr(stock_analysis.api_fetcher, "get_options_chain", lambda symbol: chain)
    monkeypatch.setattr(stock_analysis.graham, "score", lambda price, facts: {"market_cap": 200})
    monkeypatch.setattr(stock_analysis.screener, "get_sector_avg_return_12m", lambda *args, **kwargs: 0)
    monkeypatch.setattr(stock_analysis.momentum, "score", lambda *args, **kwargs: {})
    monkeypatch.setattr(stock_analysis.scorer, "composite", lambda *args: {})
    monkeypatch.setattr(stock_analysis.piotroski, "score", lambda facts: {})
    monkeypatch.setattr(stock_analysis.altman, "score", lambda price, facts: {})
    monkeypatch.setattr(
        stock_analysis.risk_metrics,
        "score",
        lambda hist, spy: {"risk_score": 70, "risk_score_max": 100},
    )
    monkeypatch.setattr(stock_analysis.greenblatt, "compute_single", lambda price, facts: {})
    monkeypatch.setattr(stock_analysis.buffett, "score", lambda price, facts: {})

    monkeypatch.setattr(
        stock_analysis.profitability_model,
        "ProfitabilityAnalyzer",
        lambda *args: SimpleNamespace(get_profitability_score=lambda: {}),
    )
    monkeypatch.setattr(
        stock_analysis.fcf_quality_model,
        "FCFQualityAnalyzer",
        lambda *args: SimpleNamespace(get_fcf_quality_score=lambda: {}),
    )
    monkeypatch.setattr(
        stock_analysis.capital_allocation_model,
        "CapitalAllocationAnalyzer",
        lambda *args: SimpleNamespace(get_capital_allocation_score=lambda: {}),
    )
    monkeypatch.setattr(
        stock_analysis.growth_quality_model,
        "GrowthQualityAnalyzer",
        lambda *args: SimpleNamespace(get_growth_quality_score=lambda: {}),
    )
    monkeypatch.setattr(stock_analysis.api_fetcher, "get_insider_transactions", lambda symbol: [])
    monkeypatch.setattr(stock_analysis.insider_activity_model, "get_insider_score", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        stock_analysis.factor_momentum_model,
        "FactorMomentumAnalyzer",
        lambda *args: SimpleNamespace(get_factor_momentum_score=lambda: {}),
    )
    monkeypatch.setattr(stock_analysis.sec_data, "get_recent_8k_filings", lambda symbol: [])
    monkeypatch.setattr(stock_analysis.api_fetcher, "get_institutional_ownership_trends", lambda symbol: [])
    monkeypatch.setattr(stock_analysis.api_fetcher, "get_patent_trends", lambda symbol: [])
    monkeypatch.setattr(stock_analysis.api_fetcher, "is_finnhub_configured", lambda: True)
    monkeypatch.setattr(stock_analysis.alternative_data_model, "get_alternative_data_score", lambda *args, **kwargs: {})
    monkeypatch.setattr(stock_analysis.scorer, "enhanced_composite", lambda *args, **kwargs: {"composite_score": 70})
    monkeypatch.setattr(stock_analysis, "_get_comomentum_result", lambda: None)
    monkeypatch.setattr(stock_analysis.regime_model, "score", lambda *args, **kwargs: {"market_trend_score": 75})
    monkeypatch.setattr(stock_analysis.scorer, "apply_regime_overlay", lambda *args: {})

    def fake_options_signal(*args, **kwargs):
        captured.update(kwargs)
        return {"received_chain": kwargs.get("option_chain") is chain}

    monkeypatch.setattr(stock_analysis.options_signal_model, "get_options_signal", fake_options_signal)
    monkeypatch.setattr(stock_analysis.spy_benchmark_model, "compute_benchmark", lambda *args: {})
    monkeypatch.setattr(stock_analysis, "_get_market_fear_result", lambda: None)
    monkeypatch.setattr(stock_analysis.factor_engine, "persist_factor_scores", lambda *args, **kwargs: None)
    monkeypatch.setattr(stock_analysis.db, "record_composite_score_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(stock_analysis.db, "upsert_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(stock_analysis, "save_standard_snapshot", lambda *args, **kwargs: None)

    result = stock_analysis.analyze_stock("AAPL")
    assert result["options_signal"] == {"received_chain": True}
    assert captured["option_chain"] is chain


def test_long_lived_analysis_cache_refreshes_only_options_overlay(monkeypatch):
    chain = normalize_finnhub_chain(_payload(), "AAPL", fetched_at=FETCHED_AT).to_dict()
    cached = {
        "symbol": "AAPL",
        "price": 200.0,
        "price_history": {"Close": {0: 190.0, 1: 200.0}},
        "regime": {"market_trend_score": 75},
        "risk": {"risk_score": 70, "risk_score_max": 100, "risk_free_rate": 0.04},
        "capital_allocation": {"dividend_yield_implied": 1.5},
        "options_signal": {"chain_status": "OLD"},
    }
    captured = {}

    monkeypatch.setattr(stock_analysis.api_fetcher, "get_options_chain", lambda symbol: chain)

    def fake_options_signal(*args, **kwargs):
        captured.update(kwargs)
        return {"chain_status": "AVAILABLE"}

    monkeypatch.setattr(stock_analysis.options_signal_model, "get_options_signal", fake_options_signal)
    result = stock_analysis._refresh_cached_options_signal(cached)

    assert result is cached
    assert result["options_signal"] == {"chain_status": "AVAILABLE"}
    assert captured["option_chain"] is chain
    assert isinstance(captured["price_hist"], pd.DataFrame)
    assert captured["risk_free_rate"] == pytest.approx(0.04)
    assert captured["dividend_yield"] == pytest.approx(0.015)


def test_analysis_converts_dividend_yield_percent_for_option_pricing():
    assert stock_analysis._option_dividend_yield({"dividend_yield_implied": 2.5}) == pytest.approx(0.025)
    assert stock_analysis._option_dividend_yield({"dividend_yield_implied": None}) is None
    assert stock_analysis._option_dividend_yield({"dividend_yield_implied": 30}) is None
