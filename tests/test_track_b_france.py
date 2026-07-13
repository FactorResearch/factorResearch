import json

from codes.app_modules import screener_markets
from codes.core import app_flags
from codes.data.providers.france import FranceProviderAdapter, is_france_symbol, normalize_france_symbol
from codes.data.providers.france_ingestion import FranceVerifiedCsvBundle, load_france_verified_csv_bundle
from codes.data.providers.france_normalization import build_france_scoring_facts
from codes.data.providers.registry import provider_for_symbol


class FranceSource:
    def get_company_profile(self, symbol):
        return {"issuer_name": "Example SA", "exchange": "EURONEXT PARIS", "currency": "EUR", "lei": "969500TEST", "security_type": "ordinary_share", "accounting_standard": "IFRS"}
    def get_financial_periods(self, symbol):
        return [{"year": year, "period": "FY", "period_end": f"{year}-12-31", "currency": "EUR"} for year in (2025, 2024, 2023)]
    def get_income_statements(self, symbol):
        return [{"fiscal_year": year, "fiscal_period": "FY", "period_end": f"{year}-12-31", "chiffre_affaires": 1000, "resultat_net": 100} for year in (2025, 2024, 2023)]
    def get_balance_sheets(self, symbol):
        return [{"fiscal_year": year, "fiscal_period": "FY", "period_end": f"{year}-12-31", "total_des_actifs": 800, "total_des_passifs": 300, "capitaux_propres": 500} for year in (2025, 2024, 2023)]
    def get_cash_flows(self, symbol): return []
    def get_filings(self, symbol): return self.get_source_documents(symbol)
    def get_shares_outstanding(self, symbol): return {"shares": 100, "date": "2026-01-31", "source": "AMF"}
    def get_source_documents(self, symbol): return [{"document_id": "fr-2025-urd", "source": "AMF", "url": "https://example.test/fr", "filing_date": "2026-02-01", "period_end": "2025-12-31", "confidence": "regulatory_verified"}]
    def get_statement_provenance(self, symbol):
        return [{"fact_name": field, "source_document_id": "fr-2025-urd", "confidence": "regulatory_verified", "accounting_standard": "IFRS", "fiscal_year": 2025, "fiscal_period": "FY"} for field in ("chiffre_affaires", "resultat_net", "total_des_actifs", "total_des_passifs", "capitaux_propres")]


def test_france_adapter_and_deterministic_french_mapping():
    assert normalize_france_symbol("ai:euronext") == "AI.PA"
    assert is_france_symbol("AI.PA")
    result = build_france_scoring_facts(FranceProviderAdapter(FranceSource()), "ai:euronext")
    assert result.can_score is True
    assert result.sec_facts["source_market"] == "FR"
    assert result.sec_facts["revenue"][0]["value"] == 1000
    assert result.sec_facts["equity"][0]["value"] == 500


def test_france_market_flag_and_route(monkeypatch, tmp_path):
    flag_file = tmp_path / "feature_flags.json"
    flag_file.write_text(json.dumps({"flag": "INTERNAL", "markets": {"US": True, "CA": False, "FR": True}}))
    monkeypatch.setattr(app_flags, "_FLAG_FILE", flag_file)
    assert screener_markets.market_from_path("/screener/france").code == "FR"
    assert isinstance(provider_for_symbol("AI.PA"), FranceProviderAdapter)


def test_france_verified_bundle_preserves_french_field_names(tmp_path):
    files = {
        "company.csv": "symbol,name,exchange,currency,lei,security_type,accounting_standard\nAI.PA,Example SA,EURONEXT PARIS,EUR,969500TEST,ordinary_share,IFRS\n",
        "periods.csv": "symbol,fiscal_year,fiscal_period,period_end,currency\nAI.PA,2025,FY,2025-12-31,EUR\n",
        "documents.csv": "document_id,source,url,filing_date,period_end,form,confidence\nfr-2025,AMF,https://example.test/fr,2026-02-01,2025-12-31,urd,regulatory_verified\n",
        "facts.csv": "symbol,statement_type,fact_name,fiscal_year,fiscal_period,period_end,currency,value,source_document_id,source_url,confidence,accounting_standard\nAI.PA,income,chiffre_affaires,2025,FY,2025-12-31,EUR,1000,fr-2025,https://example.test/fr,regulatory_verified,IFRS\n",
        "shares.csv": "symbol,shares_outstanding,as_of,source\nAI.PA,100,2026-01-31,AMF\n",
    }
    for name, body in files.items(): (tmp_path / name).write_text(body)
    financials, shares = load_france_verified_csv_bundle("AI.PA", FranceVerifiedCsvBundle(*(tmp_path / name for name in files)))
    assert financials.income_statement[0]["chiffre_affaires"] == 1000
    assert financials.provenance[0].source_document_id == "fr-2025"
    assert shares.shares_outstanding == 100
