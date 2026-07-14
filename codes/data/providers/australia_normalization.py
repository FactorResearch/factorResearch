"""Australia document-first fact normalization. Unknown labels fail closed."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from typing import Any
from . import DataQualityIssue,DataQualityReport
from .australia import normalize_australia_symbol
PUBLIC_CONFIDENCE={"regulatory_verified","issuer_verified","licensed_source_verified","cross_checked"};INTERNAL_CONFIDENCE="provider_normalized_internal_only"
ALIASES={"revenue":("revenue","sales"),"net_inc":("net_inc","net_income","earnings"),"earnings":("earnings","net_income","net_inc"),"eps":("eps","basic_eps","earnings_per_share"),"op_income":("op_income","operating_income"),"cur_ast":("cur_ast","current_assets"),"cur_lib":("cur_lib","current_liabilities"),"cash":("cash","cash_and_equivalents"),"lt_debt":("lt_debt","long_term_debt"),"tot_lib":("tot_lib","total_liabilities","liabilities"),"total_assets":("total_assets","assets"),"equity":("equity","shareholders_equity","total_equity"),"op_cf":("op_cf","operating_cash_flow"),"cashflow":("cashflow","operating_cash_flow","op_cf"),"capex":("capex","capital_expenditure")}
@dataclass(frozen=True)
class AustraliaNormalizationResult: symbol:str;can_score:bool;sec_facts:dict[str,Any];quality_report:DataQualityReport
def build_australia_scoring_facts(provider,symbol,*,allow_internal=False):
 s=normalize_australia_symbol(symbol);f,sh=provider.get_financials(s),provider.get_shares_outstanding(s);issues=[];p=_prov(f)
 c=f.company
 if not c.regulator_id:issues.append(_issue("missing_regulator_id","Australia issuer needs an LEI, ASIC identifier, or issuer identifier.","regulator_id"))
 if str(c.exchange or "").upper() not in {"ASX","XASX"}:issues.append(_issue("unsupported_exchange","Australia issuer exchange must be ASX or XASX.","exchange"))
 if c.security_type!="ordinary_share":issues.append(_issue("unsupported_security_type","Australia public scoring supports ordinary shares only.","security_type"))
 if not f.source_documents:issues.append(_issue("missing_source_documents","Australia financials need source documents."))
 if not allow_internal and f.source_documents and not any(x in d.source.upper() for d in f.source_documents for x in ("ASX","ASIC","ISSUER","LICENSED")):issues.append(_issue("unverified_australia_source","Public scoring requires ASX, ASIC, issuer, or licensed-source evidence.","source_documents"))
 annual={(x.fiscal_year,x.period_end) for x in f.periods if x.fiscal_period.upper()=="FY"}
 if len(annual)<3:issues.append(_issue("insufficient_annual_history","Australia scoring needs three annual periods.","periods"))
 currencies={x.currency for x in f.periods if x.currency}
 if len(currencies)!=1:issues.append(_issue("invalid_reporting_currency","Australia scoring needs one explicit reporting currency.","currency"))
 for field in ("revenue","net_inc","total_assets","tot_lib","equity"):
  rows=_rows(f,field);item=p.get(field)
  if not rows:issues.append(_issue("missing_required_fact",f"Missing required Australia fact: {field}.",field))
  elif len({(x.get("fiscal_year"),x.get("period_end")) for x in rows})<3:issues.append(_issue("insufficient_fact_history",f"Australia fact {field} needs three annual periods.",field))
  if item is None or item.confidence not in PUBLIC_CONFIDENCE and not(allow_internal and item.confidence==INTERNAL_CONFIDENCE):issues.append(_issue("weak_fact_provenance",f"Australia fact {field} needs accepted provenance.",field))
  elif str(item.accounting_standard or "").upper() not in {"IFRS","AASB","AUSTRALIAN ACCOUNTING STANDARDS","AUSTRALIAN IFRS"}:issues.append(_issue("unsupported_accounting_standard",f"Australia fact {field} needs IFRS-equivalent mapping.",field))
 if not sh.shares_outstanding or sh.shares_outstanding<=0 or not sh.as_of or not sh.source:issues.append(_issue("missing_shares_evidence","Australia scoring needs positive, dated sourced shares.","shares"))
 report=DataQualityReport("AU",not issues,_confidence(f),tuple(issues));facts=_facts(f,sh,report) if report.can_score else {};return AustraliaNormalizationResult(s,report.can_score,facts,report)
def _facts(f,sh,report):
 r={"name":f.company.name or f.company.symbol,"sector":None,"source_market":"AU","source_country":"Australia","normalization_confidence":report.confidence,"can_score":report.can_score,"data_quality_issues":[asdict(x) for x in report.issues],"regulator_id":f.company.regulator_id,"security_type":f.company.security_type,"accounting_standard":f.company.accounting_standard}
 p=_prov(f)
 for field in ALIASES:
  rows=_rows(f,field)
  if rows:r[field]=[{"value":_value(x,field),"year":x.get("fiscal_year"),"end":x.get("period_end"),"currency":x.get("currency") or f.company.currency,"source_market":"AU","source_document_id":p[field].source_document_id,"confidence":p[field].confidence} for x in rows]
 period=f.periods[0] if f.periods else None;r["shares"]=[{"value":sh.shares_outstanding,"end":sh.as_of,"year":period.fiscal_year if period else None,"currency":period.currency if period else f.company.currency,"source_market":"AU","source":sh.source,"confidence":report.confidence}];return r
def _rows(f,field):return [x for x in (*f.income_statement,*f.balance_sheet,*f.cash_flow) if _value(x,field) is not None]
def _value(row,field):
 for x in ALIASES[field]:
  try:
   if row.get(x) is not None:return float(row[x])
  except (TypeError,ValueError):pass
 return None
def _prov(f):return {field:x for x in f.provenance for field,names in ALIASES.items() if x.fact_name in names}
def _confidence(f):
 vals=[x.confidence for x in (*f.source_documents,*f.provenance)];return next((x for x in ("regulatory_verified","issuer_verified","licensed_source_verified","cross_checked") if x in vals),"insufficient_source_evidence")
def _issue(c,m,f=None):return DataQualityIssue(c,m,"error",f)
