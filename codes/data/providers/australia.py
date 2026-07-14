"""Australia market provider adapter; acquisition remains outside the web app."""
from __future__ import annotations
from typing import Any, Protocol
from . import CanonicalCompany, CanonicalCurrency, CanonicalFinancials, CanonicalFiscalPeriod, CanonicalSharesOutstanding, FilingDocument, StatementProvenance
class AustraliaDataSource(Protocol):
 def get_company_profile(self,symbol:str)->dict[str,Any]|None: ...
 def get_financial_periods(self,symbol:str)->list[dict[str,Any]]: ...
 def get_income_statements(self,symbol:str)->list[dict[str,Any]]: ...
 def get_balance_sheets(self,symbol:str)->list[dict[str,Any]]: ...
 def get_cash_flows(self,symbol:str)->list[dict[str,Any]]: ...
 def get_filings(self,symbol:str)->list[dict[str,Any]]: ...
 def get_shares_outstanding(self,symbol:str)->dict[str,Any]|None: ...
 def get_source_documents(self,symbol:str)->list[dict[str,Any]]: ...
 def get_statement_provenance(self,symbol:str)->list[dict[str,Any]]: ...
class EmptyAustraliaDataSource:
 def get_company_profile(self,s):return None
 def get_financial_periods(self,s):return []
 def get_income_statements(self,s):return []
 def get_balance_sheets(self,s):return []
 def get_cash_flows(self,s):return []
 def get_filings(self,s):return []
 def get_shares_outstanding(self,s):return None
 def get_source_documents(self,s):return []
 def get_statement_provenance(self,s):return []
class AustraliaProviderAdapter:
 provider_name,country,default_currency="australia","Australia","AUD";supported_exchanges=("ASX","XASX")
 def __init__(self,source=None):self.source=source or EmptyAustraliaDataSource()
 def get_company(self,symbol):
  s=normalize_australia_symbol(symbol);r=self.source.get_company_profile(s) or {};return CanonicalCompany(s,r.get("name") or r.get("issuer_name"),r.get("exchange"),self.country,r.get("currency") or self.default_currency,r.get("regulator_id") or r.get("lei") or r.get("asic_id"),r.get("security_type"),r.get("accounting_standard"))
 def get_financials(self,symbol):
  s=normalize_australia_symbol(symbol);c=self.get_company(s);return CanonicalFinancials(c,tuple(x for r in self.source.get_financial_periods(s) if (x:=_period(r,c.currency))),tuple(self.source.get_income_statements(s)),tuple(self.source.get_balance_sheets(s)),tuple(self.source.get_cash_flows(s)),tuple(self.get_source_documents(s)),tuple(self.get_statement_provenance(s)))
 def get_filings(self,s):return list(self.source.get_filings(normalize_australia_symbol(s)))
 def get_shares_outstanding(self,s):
  s=normalize_australia_symbol(s);r=self.source.get_shares_outstanding(s) or {};return CanonicalSharesOutstanding(s,_num(r.get("shares_outstanding") or r.get("shares")),r.get("as_of") or r.get("date"),r.get("source"))
 def get_shares(self,s):
  x=self.get_shares_outstanding(s);return {"symbol":x.symbol,"shares_outstanding":x.shares_outstanding,"as_of":x.as_of,"source":x.source}
 def get_source_documents(self,s):return [_document(r) for r in self.source.get_source_documents(normalize_australia_symbol(s))]
 def get_statement_provenance(self,s):return [_provenance(r) for r in self.source.get_statement_provenance(normalize_australia_symbol(s))]
 def get_currency(self,s):return self.get_company(s).currency
 def get_currency_info(self,s):return CanonicalCurrency(self.get_currency(s) or self.default_currency,"Australian dollar")
def normalize_australia_symbol(symbol):
 v=str(symbol or "").upper().strip().replace(":",".");return v[:-4]+".AX" if v.endswith(".ASX") else v
def is_australia_symbol(symbol):return normalize_australia_symbol(symbol).endswith(".AX")
def _period(r,fallback):
 try:y=int(r.get("fiscal_year") or r.get("year"))
 except (TypeError,ValueError):return None
 e=r.get("period_end") or r.get("end_date");return CanonicalFiscalPeriod(y,str(r.get("fiscal_period") or r.get("period") or "FY"),str(e),r.get("currency") or fallback) if e else None
def _document(r):return FilingDocument(str(r.get("document_id") or r.get("id") or ""),str(r.get("source") or "unknown"),r.get("url"),r.get("filing_date") or r.get("date"),r.get("period_end"),r.get("form") or r.get("document_type"),r.get("confidence") or "insufficient_source_evidence")
def _provenance(r):
 try:y=int(r.get("fiscal_year") or r.get("year"))
 except (TypeError,ValueError):y=None
 return StatementProvenance(str(r.get("fact_name") or r.get("field") or ""),str(r.get("source_document_id") or r.get("document_id") or ""),r.get("source_url") or r.get("url"),r.get("confidence") or "insufficient_source_evidence",r.get("accounting_standard"),r.get("extraction_method"),r.get("normalization_method"),y,r.get("fiscal_period") or r.get("period"))
def _num(v):
 try:return float(v)
 except (TypeError,ValueError):return None
