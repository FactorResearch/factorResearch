"""Australia relational database adapter; no JSON persistence."""
from codes.data import db
from .australia import normalize_australia_symbol
from .australia_normalization import PUBLIC_CONFIDENCE,build_australia_scoring_facts
from .australia import AustraliaProviderAdapter
from .screener_projection import build_fundamental_screener_projection
class AustraliaDatabaseDataSource:
 def get_company_profile(self,s):return db.get_market_company_profile("AU",normalize_australia_symbol(s))
 def get_financial_periods(self,s):return db.get_market_fiscal_periods("AU",normalize_australia_symbol(s))
 def get_income_statements(self,s):return db.get_market_statement_facts("AU",normalize_australia_symbol(s),"income")
 def get_balance_sheets(self,s):return db.get_market_statement_facts("AU",normalize_australia_symbol(s),"balance")
 def get_cash_flows(self,s):return db.get_market_statement_facts("AU",normalize_australia_symbol(s),"cash_flow")
 def get_filings(self,s):return self.get_source_documents(s)
 def get_shares_outstanding(self,s):return db.get_market_shares_outstanding("AU",normalize_australia_symbol(s))
 def get_source_documents(self,s):return db.get_market_source_documents("AU",normalize_australia_symbol(s))
 def get_statement_provenance(self,s):return db.get_market_statement_provenance("AU",normalize_australia_symbol(s))
def materialize_australia_screener_projection(symbol):
 s=normalize_australia_symbol(symbol);p=AustraliaProviderAdapter(AustraliaDatabaseDataSource());r=build_australia_scoring_facts(p,s)
 if not r.can_score or r.quality_report.confidence not in PUBLIC_CONFIDENCE:db.delete_market_screener_row("AU",s);return False
 f=p.get_financials(s);c=f.company;db.upsert_market_screener_row("AU",s,build_fundamental_screener_projection(market_code="AU",symbol=s,name=c.name,sector=None,currency=c.currency or "AUD",sec_facts=r.sec_facts,data_confidence=r.quality_report.confidence));return True
