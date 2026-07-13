import json
from importlib import reload

from codes.app_modules import screener_markets
from codes.core import app_flags
from codes.data.providers.germany import GermanyProviderAdapter, is_germany_symbol, normalize_germany_symbol
from codes.data.providers.germany_ingestion import GermanyVerifiedCsvBundle, load_germany_verified_csv_bundle
from codes.data.providers.germany_normalization import build_germany_scoring_facts
from codes.data.providers.registry import provider_for_symbol


class GermanySource:
    def get_company_profile(self, symbol):
        return {"issuer_name": "Example AG", "exchange": "XETRA", "currency": "EUR", "lei": "529900TEST", "security_type": "ordinary_share", "accounting_standard": "IFRS"}
    def get_financial_periods(self, symbol):
        return [{"year": year, "period": "FY", "period_end": f"{year}-12-31", "currency": "EUR"} for year in (2025, 2024, 2023)]
    def get_income_statements(self, symbol):
        return [{"fiscal_year": year, "fiscal_period": "FY", "period_end": f"{year}-12-31", "umsatzerloese": 1000, "jahresueberschuss": 100} for year in (2025, 2024, 2023)]
    def get_balance_sheets(self, symbol):
        return [{"fiscal_year": year, "fiscal_period": "FY", "period_end": f"{year}-12-31", "bilanzsumme": 800, "verbindlichkeiten": 300, "eigenkapital": 500} for year in (2025, 2024, 2023)]
    def get_cash_flows(self, symbol): return []
    def get_filings(self, symbol): return self.get_source_documents(symbol)
    def get_shares_outstanding(self, symbol): return {"shares": 100, "date": "2026-01-31", "source": "Bundesanzeiger"}
    def get_source_documents(self, symbol): return [{"document_id": "de-2025-ar", "source": "Bundesanzeiger", "url": "https://example.test/de", "filing_date": "2026-02-01", "period_end": "2025-12-31", "confidence": "regulatory_verified"}]
    def get_statement_provenance(self, symbol):
        return [{"fact_name": field, "source_document_id": "de-2025-ar", "confidence": "regulatory_verified", "accounting_standard": "IFRS", "fiscal_year": 2025, "fiscal_period": "FY"} for field in ("umsatzerloese", "jahresueberschuss", "bilanzsumme", "verbindlichkeiten", "eigenkapital")]


def test_germany_symbol_adapter_and_deterministic_german_mapping():
    assert normalize_germany_symbol("sap:xetra") == "SAP.DE"
    assert is_germany_symbol("SAP.DE")
    result = build_germany_scoring_facts(GermanyProviderAdapter(GermanySource()), "sap:xetra")
    assert result.can_score is True
    assert result.sec_facts["source_market"] == "DE"
    assert result.sec_facts["revenue"][0]["value"] == 1000
    assert result.sec_facts["equity"][0]["value"] == 500


def test_germany_market_flag_and_route(monkeypatch, tmp_path):
    flag_file = tmp_path / "feature_flags.json"
    flag_file.write_text(json.dumps({"flag": "INTERNAL", "markets": {"US": True, "CA": False, "DE": True}}))
    monkeypatch.setattr(app_flags, "_FLAG_FILE", flag_file)
    reload(screener_markets)
    assert screener_markets.market_from_path("/screener/germany").code == "DE"
    assert isinstance(provider_for_symbol("SAP.DE"), GermanyProviderAdapter)
    flag_file.write_text(json.dumps({"flag": "INTERNAL", "markets": {"US": True, "CA": False, "DE": False}}))
    reload(screener_markets)


def test_germany_verified_bundle_preserves_german_field_names(tmp_path):
    files = {
        "company.csv": "symbol,name,exchange,currency,lei,security_type,accounting_standard\nSAP.DE,Example AG,XETRA,EUR,529900TEST,ordinary_share,IFRS\n",
        "periods.csv": "symbol,fiscal_year,fiscal_period,period_end,currency\nSAP.DE,2025,FY,2025-12-31,EUR\n",
        "documents.csv": "document_id,source,url,filing_date,period_end,form,confidence\nde-2025,Bundesanzeiger,https://example.test/de,2026-02-01,2025-12-31,annual,regulatory_verified\n",
        "facts.csv": "symbol,statement_type,fact_name,fiscal_year,fiscal_period,period_end,currency,value,source_document_id,source_url,confidence,accounting_standard\nSAP.DE,income,umsatzerloese,2025,FY,2025-12-31,EUR,1000,de-2025,https://example.test/de,regulatory_verified,IFRS\n",
        "shares.csv": "symbol,shares_outstanding,as_of,source\nSAP.DE,100,2026-01-31,Bundesanzeiger\n",
    }
    for name, body in files.items():
        (tmp_path / name).write_text(body)
    bundle = GermanyVerifiedCsvBundle(*(tmp_path / name for name in files))
    financials, shares = load_germany_verified_csv_bundle("SAP.DE", bundle)
    assert financials.income_statement[0]["umsatzerloese"] == 1000
    assert financials.provenance[0].source_document_id == "de-2025"
    assert shares.shares_outstanding == 100
