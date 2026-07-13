"""Deterministic Netherlands filing normalization and scoring gates."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any
from . import CanonicalFinancials, CanonicalSharesOutstanding, DataQualityIssue, DataQualityReport
from .netherlands import NetherlandsProviderAdapter, normalize_netherlands_symbol

PUBLIC_CONFIDENCE = {"regulatory_verified", "issuer_verified", "licensed_source_verified", "cross_checked"}
INTERNAL_CONFIDENCE = "provider_normalized_internal_only"
REQUIRED_FIELDS = ("revenue", "net_inc", "total_assets", "tot_lib", "equity")
SUPPORTED_STANDARDS = {"IFRS", "EU-ADOPTED IFRS", "DUTCH GAAP"}
ALIASES = {
    "revenue": ("revenue", "sales", "netto_omzet", "omzet"), "net_inc": ("net_inc", "net_income", "earnings", "nettoresultaat"),
    "earnings": ("earnings", "net_income", "net_inc", "nettoresultaat"), "eps": ("eps", "basic_eps", "earnings_per_share", "winst_per_aandeel"),
    "op_income": ("op_income", "operating_income", "bedrijfsresultaat"), "ebit": ("ebit", "resultaat_voor_rente_en_belastingen"),
    "cur_ast": ("cur_ast", "current_assets", "vlottende_activa"), "cur_lib": ("cur_lib", "current_liabilities", "kortlopende_schulden"),
    "cash": ("cash", "cash_and_equivalents", "liquide_middelen"), "lt_debt": ("lt_debt", "long_term_debt", "langlopende_schulden"),
    "tot_lib": ("tot_lib", "total_liabilities", "liabilities", "totaal_verplichtingen"), "total_assets": ("total_assets", "assets", "totaal_activa"),
    "equity": ("equity", "shareholders_equity", "total_equity", "eigen_vermogen"), "bvps": ("bvps", "book_value_per_share", "boekwaarde_per_aandeel"),
    "op_cf": ("op_cf", "operating_cash_flow", "kasstroom_uit_operationele_activiteiten"), "cashflow": ("cashflow", "operating_cash_flow", "op_cf"), "capex": ("capex", "capital_expenditure", "investeringen"),
}

@dataclass(frozen=True)
class NetherlandsNormalizationResult:
    symbol: str; can_score: bool; sec_facts: dict[str, Any]; quality_report: DataQualityReport

def build_netherlands_scoring_facts(provider: NetherlandsProviderAdapter, symbol: str, *, allow_internal=False):
    symbol = normalize_netherlands_symbol(symbol); financials, shares = provider.get_financials(symbol), provider.get_shares_outstanding(symbol)
    issues = _validate(financials, shares, allow_internal); report = DataQualityReport("NL", not any(x.severity == "error" for x in issues), _confidence(financials), tuple(issues))
    return NetherlandsNormalizationResult(symbol, report.can_score, _facts(financials, shares, report) if report.can_score else {}, report)

def _validate(financials, shares, internal):
    issues=[]; company=financials.company; provenance=_provenance(financials)
    if not company.regulator_id: issues.append(_issue("missing_regulator_id", "Netherlands issuer needs an LEI, AFM identifier, or issuer identifier.", "regulator_id"))
    if str(company.exchange or "").upper() not in {"EURONEXT AMSTERDAM", "XAMS"}: issues.append(_issue("unsupported_exchange", "Netherlands issuer exchange must be Euronext Amsterdam or XAMS.", "exchange"))
    if company.security_type != "ordinary_share": issues.append(_issue("unsupported_security_type", "Netherlands public scoring supports ordinary shares only.", "security_type"))
    if not financials.source_documents: issues.append(_issue("missing_source_documents", "Netherlands financials need source filing documents."))
    if not internal and financials.source_documents and not any(marker in x.source.upper() for x in financials.source_documents for marker in ("AFM", "EURONEXT", "ISSUER", "LICENSED")): issues.append(_issue("unverified_netherlands_source", "Public scoring requires AFM, Euronext Amsterdam, issuer, or licensed-source evidence.", "source_documents"))
    if any(not _confidence_allowed(x.confidence, internal) for x in financials.source_documents): issues.append(_issue("weak_document_confidence", "Source document is not public-score quality.", "source_documents"))
    annual={(x.fiscal_year,x.period_end) for x in financials.periods if x.fiscal_period.upper()=="FY"}
    if len(annual)<3: issues.append(_issue("insufficient_annual_history", "Netherlands scoring needs three annual periods.", "periods"))
    currencies={str(x.currency).upper() for x in financials.periods if x.currency}
    if any(not x.currency for x in financials.periods) or len(currencies)>1: issues.append(_issue("invalid_reporting_currency", "Netherlands scoring needs one explicit reporting currency.", "currency"))
    for field in REQUIRED_FIELDS:
        rows,item=_records(financials,field),provenance.get(field)
        if not rows: issues.append(_issue("missing_required_fact", f"Missing required Netherlands fact: {field}.", field))
        elif len(_annual(rows))<3: issues.append(_issue("insufficient_fact_history", f"Netherlands fact {field} needs three annual periods.", field))
        if item is None: issues.append(_issue("missing_fact_provenance", f"Missing provenance for Netherlands fact: {field}.", field))
        elif not _confidence_allowed(item.confidence, internal): issues.append(_issue("weak_fact_confidence", f"Weak provenance for Netherlands fact: {field}.", field))
        elif _standard(item.accounting_standard) not in SUPPORTED_STANDARDS: issues.append(_issue("unsupported_accounting_standard", f"Netherlands fact {field} needs IFRS or Dutch GAAP mapping.", field))
    if not shares.shares_outstanding or shares.shares_outstanding<=0 or not shares.as_of or not shares.source: issues.append(_issue("missing_shares_evidence", "Netherlands scoring needs positive, dated sourced shares.", "shares"))
    for row in financials.balance_sheet:
        assets,liabilities,equity=(_value(row,x) for x in ("total_assets","tot_lib","equity"))
        if None not in (assets,liabilities,equity) and abs(assets-(liabilities+equity))>max(abs(assets)*.01,1): issues.append(_issue("balance_sheet_not_reconciled", "Netherlands balance sheet does not reconcile.", "balance_sheet"))
    return issues

def _facts(financials, shares, report):
    provenance=_provenance(financials); result={"name":financials.company.name or financials.company.symbol,"sector":None,"source_market":"NL","source_country":"Netherlands","source_regulator":_regulator(financials),"normalization_confidence":report.confidence,"can_score":report.can_score,"data_quality_issues":[asdict(x) for x in report.issues],"regulator_id":financials.company.regulator_id,"security_type":financials.company.security_type,"accounting_standard":financials.company.accounting_standard}
    for field in ALIASES:
        rows=_records(financials,field)
        if rows: result[field]=[_record(x,field,financials,provenance.get(field)) for x in rows]
    period=financials.periods[0] if financials.periods else None; result["shares"]=[{"value":shares.shares_outstanding,"end":shares.as_of,"year":period.fiscal_year if period else None,"currency":period.currency if period else financials.company.currency,"source_market":"NL","source":shares.source,"confidence":report.confidence}]
    if "bvps" not in result and result.get("equity"): result["bvps"]=[{**result["equity"][0],"value":result["equity"][0]["value"]/shares.shares_outstanding,"source":shares.source,"normalization_method":"equity_divided_by_shares_outstanding"}]
    return result
def _record(row,field,financials,item):
    result={"value":_value(row,field),"year":row.get("fiscal_year") or row.get("year"),"end":row.get("period_end") or row.get("end"),"currency":row.get("currency") or financials.company.currency,"source_market":"NL"}
    if item: result.update({"source_document_id":item.source_document_id,"source_url":item.source_url,"confidence":item.confidence,"accounting_standard":item.accounting_standard})
    return result
def _records(financials,field): return [x for x in (*financials.income_statement,*financials.balance_sheet,*financials.cash_flow) if _value(x,field) is not None]
def _value(row,field):
    for name in ALIASES.get(field,(field,)):
        try:
            if row.get(name) is not None:return float(row[name])
        except (TypeError,ValueError):pass
    return None
def _annual(rows): return {(x.get("fiscal_year") or x.get("year"),x.get("period_end") or x.get("end")) for x in rows if str(x.get("fiscal_period") or x.get("period") or "FY").upper()=="FY"}
def _provenance(financials): return {field:item for item in financials.provenance for field,names in ALIASES.items() if item.fact_name in names}
def _standard(value): return {"INTERNATIONAL FINANCIAL REPORTING STANDARDS":"IFRS","EU ADOPTED IFRS":"EU-ADOPTED IFRS","DUTCH GENERALLY ACCEPTED ACCOUNTING PRINCIPLES":"DUTCH GAAP"}.get(str(value or "").upper().replace("_"," ").strip(),str(value or "").upper())
def _confidence_allowed(value,internal): return value in PUBLIC_CONFIDENCE or (internal and value==INTERNAL_CONFIDENCE)
def _confidence(financials):
    values=[x.confidence for x in (*financials.source_documents,*financials.provenance)]
    if INTERNAL_CONFIDENCE in values:return INTERNAL_CONFIDENCE
    return next((x for x in ("regulatory_verified","issuer_verified","licensed_source_verified","cross_checked") if x in values),"insufficient_source_evidence")
def _regulator(financials):
    sources={x.source.upper() for x in financials.source_documents}
    return "AFM" if any("AFM" in x for x in sources) else "Euronext Amsterdam" if any("EURONEXT" in x for x in sources) else "issuer filing" if any("ISSUER" in x for x in sources) else "verified source"
def _issue(code,message,field=None): return DataQualityIssue(code,message,"error",field)
