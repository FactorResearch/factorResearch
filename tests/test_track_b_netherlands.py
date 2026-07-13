import json
from codes.app_modules import screener_markets
from codes.core import app_flags
from codes.data.providers.netherlands import NetherlandsProviderAdapter,is_netherlands_symbol,normalize_netherlands_symbol
from codes.data.providers.netherlands_normalization import build_netherlands_scoring_facts
from codes.data.providers.registry import provider_for_symbol
class Source:
    def get_company_profile(self,s):return {"issuer_name":"Example NV","exchange":"EURONEXT AMSTERDAM","currency":"EUR","lei":"724500TEST","security_type":"ordinary_share","accounting_standard":"IFRS"}
    def get_financial_periods(self,s):return [{"year":y,"period":"FY","period_end":f"{y}-12-31","currency":"EUR"} for y in (2025,2024,2023)]
    def get_income_statements(self,s):return [{"fiscal_year":y,"fiscal_period":"FY","period_end":f"{y}-12-31","netto_omzet":1000,"nettoresultaat":100} for y in (2025,2024,2023)]
    def get_balance_sheets(self,s):return [{"fiscal_year":y,"fiscal_period":"FY","period_end":f"{y}-12-31","totaal_activa":800,"totaal_verplichtingen":300,"eigen_vermogen":500} for y in (2025,2024,2023)]
    def get_cash_flows(self,s):return []
    def get_filings(self,s):return self.get_source_documents(s)
    def get_shares_outstanding(self,s):return {"shares":100,"date":"2026-01-31","source":"AFM"}
    def get_source_documents(self,s):return [{"document_id":"nl-2025","source":"AFM","filing_date":"2026-02-01","confidence":"regulatory_verified"}]
    def get_statement_provenance(self,s):return [{"fact_name":x,"source_document_id":"nl-2025","confidence":"regulatory_verified","accounting_standard":"IFRS","fiscal_year":2025,"fiscal_period":"FY"} for x in ("netto_omzet","nettoresultaat","totaal_activa","totaal_verplichtingen","eigen_vermogen")]
def test_netherlands_mapping():
    assert normalize_netherlands_symbol("asml:euronext")=="ASML.AS" and is_netherlands_symbol("ASML.AS")
    r=build_netherlands_scoring_facts(NetherlandsProviderAdapter(Source()),"asml:euronext")
    assert r.can_score and r.sec_facts["source_market"]=="NL" and r.sec_facts["equity"][0]["value"]==500
def test_netherlands_flag(monkeypatch,tmp_path):
    p=tmp_path/"feature_flags.json";p.write_text(json.dumps({"flag":"INTERNAL","markets":{"US":True,"CA":False,"NL":True}}));monkeypatch.setattr(app_flags,"_FLAG_FILE",p)
    assert screener_markets.market_from_path("/screener/netherlands").code=="NL" and isinstance(provider_for_symbol("ASML.AS"),NetherlandsProviderAdapter)
