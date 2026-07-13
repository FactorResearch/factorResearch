from importlib import reload
import json

from codes.app_modules import screener_markets
from codes.core import app_flags
from codes.data.providers import CanonicalFinancials, CanonicalSharesOutstanding
from codes.data.providers.canada import (
    CanadaProviderAdapter,
    is_canadian_symbol,
    normalize_canada_symbol,
)
from codes.data.providers.canada_normalization import build_canada_scoring_facts
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
        return [{
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "currency": "CAD",
            "revenue": 1_000_000,
            "net_inc": 120_000,
            "op_income": 160_000,
        }]

    def get_balance_sheets(self, symbol):
        return [{
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "currency": "CAD",
            "total_assets": 800_000,
            "tot_lib": 300_000,
            "equity": 500_000,
            "cur_ast": 250_000,
            "cur_lib": 100_000,
        }]

    def get_cash_flows(self, symbol):
        return [{
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "currency": "CAD",
            "operating_cash_flow": 150_000,
            "capex": 40_000,
        }]

    def get_filings(self, symbol):
        return [{"form": "Annual financial statements", "source": "SEDAR+"}]

    def get_shares_outstanding(self, symbol):
        return {"shares": "1234", "date": "2026-01-31", "source": "fixture"}

    def get_source_documents(self, symbol):
        return [{
            "document_id": "sedar-2025-ar",
            "source": "SEDAR+",
            "url": "https://example.test/sedar/shop-2025",
            "filing_date": "2026-02-15",
            "period_end": "2025-12-31",
            "form": "Annual financial statements",
            "confidence": "regulatory_verified",
        }]

    def get_statement_provenance(self, symbol):
        fields = ("revenue", "net_inc", "total_assets", "tot_lib", "equity")
        return [{
            "fact_name": field,
            "source_document_id": "sedar-2025-ar",
            "source_url": "https://example.test/sedar/shop-2025",
            "confidence": "regulatory_verified",
            "accounting_standard": "IFRS",
            "extraction_method": "fixture",
            "normalization_method": "canada_v1",
        } for field in fields]


class ProviderNormalizedOnlySource(FakeCanadaSource):
    def get_source_documents(self, symbol):
        rows = super().get_source_documents(symbol)
        rows[0]["confidence"] = "provider_normalized_internal_only"
        return rows

    def get_statement_provenance(self, symbol):
        rows = super().get_statement_provenance(symbol)
        for row in rows:
            row["confidence"] = "provider_normalized_internal_only"
        return rows


class BrokenBalanceSheetSource(FakeCanadaSource):
    def get_balance_sheets(self, symbol):
        rows = super().get_balance_sheets(symbol)
        rows[0]["equity"] = 200_000
        return rows


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
    assert financials.income_statement[0]["revenue"] == 1_000_000
    assert financials.source_documents[0].confidence == "regulatory_verified"
    assert financials.provenance[0].accounting_standard == "IFRS"
    assert isinstance(shares, CanonicalSharesOutstanding)
    assert shares.shares_outstanding == 1234.0
    assert provider.get_listing_information("shop:tsx")["exchange"] == "TSX"


def test_canada_market_is_feature_gated(monkeypatch, tmp_path):
    def set_markets(markets):
        flag_file = tmp_path / "feature_flags.json"
        flag_file.write_text(json.dumps({"flag": "INTERNAL", "markets": markets}))
        monkeypatch.setattr(app_flags, "_FLAG_FILE", flag_file)

    set_markets({"US": True, "CA": False})
    reload(screener_markets)

    assert screener_markets.get_screener_country("CA")["code"] == "US"
    assert provider_for_symbol("SHOP.TO") is None

    set_markets({"US": True, "CA": True})
    reload(screener_markets)

    assert screener_markets.get_screener_country("CA")["code"] == "CA"
    assert screener_markets.row_matches_country({"country": "Canada"}, "CA") is True
    assert isinstance(provider_for_symbol("SHOP.TO"), CanadaProviderAdapter)

    set_markets({"US": True, "CA": False})
    reload(screener_markets)


def test_canada_verified_data_builds_score_ready_facts():
    provider = CanadaProviderAdapter(FakeCanadaSource())

    result = build_canada_scoring_facts(provider, "shop:tsx")

    assert result.can_score is True
    assert result.quality_report.confidence == "regulatory_verified"
    assert result.sec_facts["source_market"] == "CA"
    assert result.sec_facts["source_regulator"] == "SEDAR+"
    assert result.sec_facts["revenue"][0]["currency"] == "CAD"
    assert result.sec_facts["revenue"][0]["source_document_id"] == "sedar-2025-ar"
    assert result.sec_facts["net_inc"][0]["accounting_standard"] == "IFRS"
    assert result.sec_facts["shares"][0]["source"] == "fixture"
    assert result.sec_facts["bvps"][0]["value"] == 500_000 / 1234
    assert result.sec_facts["bvps"][0]["normalization_method"] == "equity_divided_by_shares_outstanding"


def test_canada_provider_normalized_data_is_internal_only():
    provider = CanadaProviderAdapter(ProviderNormalizedOnlySource())

    public_result = build_canada_scoring_facts(provider, "SHOP.TO")
    internal_result = build_canada_scoring_facts(provider, "SHOP.TO", allow_internal=True)

    assert public_result.can_score is False
    assert public_result.sec_facts == {}
    assert {issue.code for issue in public_result.quality_report.issues} == {
        "weak_document_confidence",
        "weak_fact_confidence",
    }
    assert internal_result.can_score is True
    assert internal_result.quality_report.confidence == "provider_normalized_internal_only"


def test_canada_balance_sheet_must_reconcile_before_scoring():
    provider = CanadaProviderAdapter(BrokenBalanceSheetSource())

    result = build_canada_scoring_facts(provider, "SHOP.TO")

    assert result.can_score is False
    assert result.sec_facts == {}
    assert "balance_sheet_not_reconciled" in {issue.code for issue in result.quality_report.issues}
