from importlib import reload

from codes.app_modules import screener_markets
from codes.data.providers import CanonicalFinancials, CanonicalSharesOutstanding
from codes.data.providers.canada import (
    CanadaProviderAdapter,
    is_canadian_symbol,
    normalize_canada_symbol,
)
from codes.data.providers.registry import provider_for_symbol


class FakeCanadaSource:
    def get_company_profile(self, symbol):
        return {
            "issuer_name": "Example Canada Corp.",
            "exchange": "TSX",
            "currency": "CAD",
        }

    def get_financial_periods(self, symbol):
        return [
            {"year": 2025, "period": "FY", "period_end": "2025-12-31"},
            {"year": "bad", "period_end": "2024-12-31"},
        ]

    def get_income_statements(self, symbol):
        return [{"revenue": 100}]

    def get_balance_sheets(self, symbol):
        return [{"assets": 200}]

    def get_cash_flows(self, symbol):
        return [{"operating_cash_flow": 50}]

    def get_filings(self, symbol):
        return [{"form": "Annual financial statements", "source": "SEDAR+"}]

    def get_shares_outstanding(self, symbol):
        return {"shares": "1234", "date": "2026-01-31", "source": "fixture"}


def test_canada_symbol_normalization_and_detection():
    assert normalize_canada_symbol("shop:tsx") == "SHOP.TO"
    assert normalize_canada_symbol("v:test:tsxv") == "V.TEST.V"
    assert is_canadian_symbol("SHOP.TO") is True
    assert is_canadian_symbol("AAPL") is False


def test_canada_provider_returns_canonical_models():
    provider = CanadaProviderAdapter(FakeCanadaSource())

    company = provider.get_company("shop:tsx")
    financials = provider.get_financials("shop:tsx")
    shares = provider.get_shares_outstanding("shop:tsx")

    assert company.symbol == "SHOP.TO"
    assert company.country == "Canada"
    assert company.currency == "CAD"
    assert isinstance(financials, CanonicalFinancials)
    assert financials.periods[0].fiscal_year == 2025
    assert financials.income_statement == ({"revenue": 100},)
    assert isinstance(shares, CanonicalSharesOutstanding)
    assert shares.shares_outstanding == 1234.0
    assert provider.get_listing_information("shop:tsx")["exchange"] == "TSX"


def test_canada_market_is_feature_gated(monkeypatch):
    monkeypatch.setenv("ENABLED_MARKETS", "US")
    reload(screener_markets)

    assert screener_markets.get_screener_country("CA")["code"] == "US"
    assert provider_for_symbol("SHOP.TO") is None

    monkeypatch.setenv("ENABLED_MARKETS", "US,CA")
    reload(screener_markets)

    assert screener_markets.get_screener_country("CA")["code"] == "CA"
    assert screener_markets.row_matches_country({"country": "Canada"}, "CA") is True
    assert isinstance(provider_for_symbol("SHOP.TO"), CanadaProviderAdapter)

    monkeypatch.setenv("ENABLED_MARKETS", "US")
    reload(screener_markets)
