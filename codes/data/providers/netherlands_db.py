"""Relational Netherlands persistence and screener projection."""
from __future__ import annotations
from typing import Any
from codes.data import db
from . import CanonicalFinancials, CanonicalSharesOutstanding
from .netherlands import NetherlandsDataSource, NetherlandsProviderAdapter, normalize_netherlands_symbol
from .netherlands_normalization import INTERNAL_CONFIDENCE, PUBLIC_CONFIDENCE, NetherlandsNormalizationResult, build_netherlands_scoring_facts
from .screener_projection import build_fundamental_screener_projection

class NetherlandsDatabaseDataSource(NetherlandsDataSource):
    def get_company_profile(self,s): return db.get_market_company_profile("NL",normalize_netherlands_symbol(s))
    def get_financial_periods(self,s): return db.get_market_financial_periods("NL",normalize_netherlands_symbol(s))
    def get_income_statements(self,s): return db.get_market_statement_facts("NL",normalize_netherlands_symbol(s),"income")
    def get_balance_sheets(self,s): return db.get_market_statement_facts("NL",normalize_netherlands_symbol(s),"balance")
    def get_cash_flows(self,s): return db.get_market_statement_facts("NL",normalize_netherlands_symbol(s),"cash_flow")
    def get_filings(self,s): return self.get_source_documents(s)
    def get_shares_outstanding(self,s): return db.get_market_shares_outstanding("NL",normalize_netherlands_symbol(s))
    def get_source_documents(self,s): return db.get_market_source_documents("NL",normalize_netherlands_symbol(s))
    def get_statement_provenance(self,s): return db.get_market_statement_provenance("NL",normalize_netherlands_symbol(s))

def ingest_verified_netherlands_financials(symbol,financials,shares,*,allow_internal=False):
    symbol=normalize_netherlands_symbol(symbol); result=build_netherlands_scoring_facts(NetherlandsProviderAdapter(_SingleIssuer(symbol,financials,shares)),symbol,allow_internal=allow_internal)
    if result.quality_report.confidence==INTERNAL_CONFIDENCE and not allow_internal: raise ValueError("Netherlands provider-normalized data requires allow_internal=True and cannot publish.")
    db.upsert_market_canonical_facts("NL",symbol,financials,shares,result.quality_report,screener_row=_projection(result,financials)); return result
def materialize_netherlands_screener_projection(symbol):
    symbol=normalize_netherlands_symbol(symbol); provider=NetherlandsProviderAdapter(NetherlandsDatabaseDataSource()); result=build_netherlands_scoring_facts(provider,symbol)
    if not result.can_score or result.quality_report.confidence not in PUBLIC_CONFIDENCE: db.delete_market_screener_row("NL",symbol); return False
    row=_projection(result,provider.get_financials(symbol))
    if row is None: db.delete_market_screener_row("NL",symbol); return False
    db.upsert_market_screener_row("NL",symbol,row); return True
def _projection(result,financials):
    if not result.can_score or result.quality_report.confidence not in PUBLIC_CONFIDENCE:return None
    c=financials.company; return build_fundamental_screener_projection(market_code="NL",symbol=result.symbol,name=c.name,sector=None,currency=c.currency or "EUR",sec_facts=result.sec_facts,data_confidence=result.quality_report.confidence)
class _SingleIssuer:
    def __init__(self,s,f,sh): self.symbol,self.financials,self.shares=s,f,sh
    def get_company_profile(self,s):
        x=self.financials.company; return {"issuer_name":x.name,"exchange":x.exchange,"country":x.country,"currency":x.currency,"regulator_id":x.regulator_id,"security_type":x.security_type,"accounting_standard":x.accounting_standard}
    def get_financial_periods(self,s): return [{"fiscal_year":x.fiscal_year,"fiscal_period":x.fiscal_period,"period_end":x.period_end,"currency":x.currency} for x in self.financials.periods]
    def get_income_statements(self,s): return list(self.financials.income_statement)
    def get_balance_sheets(self,s): return list(self.financials.balance_sheet)
    def get_cash_flows(self,s): return list(self.financials.cash_flow)
    def get_filings(self,s): return self.get_source_documents(s)
    def get_shares_outstanding(self,s): return {"shares_outstanding":self.shares.shares_outstanding,"as_of":self.shares.as_of,"source":self.shares.source}
    def get_source_documents(self,s): return [_dict(x) for x in self.financials.source_documents]
    def get_statement_provenance(self,s): return [_dict(x) for x in self.financials.provenance]
def _dict(x)->dict[str,Any]: return dict(x.__dict__)
