"""Verified Netherlands CSV imports; durable facts are relational only."""
from __future__ import annotations
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from . import CanonicalCompany,CanonicalFinancials,CanonicalFiscalPeriod,CanonicalSharesOutstanding,FilingDocument,StatementProvenance
from .netherlands import normalize_netherlands_symbol
from .netherlands_db import ingest_verified_netherlands_financials

@dataclass(frozen=True)
class NetherlandsVerifiedCsvBundle: company_csv:Path; periods_csv:Path; documents_csv:Path; facts_csv:Path; shares_csv:Path
def import_netherlands_verified_csv_bundle(symbol,bundle,*,allow_internal=False):
    financials,shares=load_netherlands_verified_csv_bundle(symbol,bundle); return ingest_verified_netherlands_financials(symbol,financials,shares,allow_internal=allow_internal)
def load_netherlands_verified_csv_bundle(symbol,bundle):
    symbol=normalize_netherlands_symbol(symbol); company=_company(symbol,bundle.company_csv); periods=tuple(_periods(symbol,bundle.periods_csv,company.currency)); docs=tuple(_documents(bundle.documents_csv)); statements,provenance=_facts(symbol,bundle.facts_csv,periods,docs,company.currency)
    return CanonicalFinancials(company,periods,tuple(statements["income"]),tuple(statements["balance"]),tuple(statements["cash_flow"]),docs,tuple(provenance)),_shares(symbol,bundle.shares_csv)
def _company(symbol,path):
    rows=_read(path)
    if len(rows)!=1:raise ValueError("Netherlands company CSV must contain exactly one row.")
    r=rows[0];_symbol(symbol,r,"company CSV");return CanonicalCompany(symbol,r.get("name") or r.get("issuer_name"),r.get("exchange"),r.get("country") or "Netherlands",(r.get("currency") or "EUR").upper(),_req(r.get("regulator_id") or r.get("lei") or r.get("afm_id"),"regulator_id"),_req(r.get("security_type"),"security_type").lower(),_req(r.get("accounting_standard"),"accounting_standard"))
def _periods(symbol,path,fallback):
    out=[];seen=set()
    for r in _read(path):
        _symbol(symbol,r,"periods CSV");x=CanonicalFiscalPeriod(_integer(r.get("fiscal_year") or r.get("year"),"fiscal_year"),(r.get("fiscal_period") or r.get("period") or "FY").upper(),_date(r.get("period_end") or r.get("end_date"),"period_end"),(r.get("currency") or fallback).upper());key=(x.fiscal_year,x.fiscal_period,x.period_end)
        if key in seen:raise ValueError(f"Netherlands periods CSV repeats fiscal period {key}.")
        seen.add(key);out.append(x)
    if not out:raise ValueError("Netherlands periods CSV must contain at least one period.")
    return sorted(out,key=lambda x:(x.fiscal_year,x.period_end),reverse=True)
def _documents(path):
    out=[];ids=set()
    for r in _read(path):
        ident=_req(r.get("document_id") or r.get("id"),"document_id")
        if ident in ids:raise ValueError(f"Netherlands documents CSV repeats document_id {ident}.")
        ids.add(ident);out.append(FilingDocument(ident,_req(r.get("source"),"source"),r.get("url"),_date(r.get("filing_date") or r.get("date"),"filing_date"),r.get("period_end"),r.get("form") or r.get("document_type"),_confidence(r.get("confidence"))))
    if not out:raise ValueError("Netherlands documents CSV must contain at least one source document.")
    return out
def _facts(symbol,path,periods,docs,fallback):
    out={x:[] for x in ("income","balance","cash_flow")}; provenance={};ids={x.document_id for x in docs};keys={(x.fiscal_year,x.fiscal_period) for x in periods}
    for r in _read(path):
        _symbol(symbol,r,"facts CSV");kind=(r.get("statement_type") or "").lower()
        if kind not in out:raise ValueError(f"Unsupported Netherlands statement_type: {kind}.")
        field=_req(r.get("fact_name") or r.get("field"),"fact_name");year=_integer(r.get("fiscal_year") or r.get("year"),"fiscal_year");period=(r.get("fiscal_period") or r.get("period") or "FY").upper();doc=_req(r.get("source_document_id") or r.get("document_id"),"source_document_id")
        if (year,period) not in keys:raise ValueError(f"Netherlands fact {field} refers to an unknown fiscal period.")
        if doc not in ids:raise ValueError(f"Netherlands fact {field} references unknown document {doc}.")
        out[kind].append({"fiscal_year":year,"fiscal_period":period,"period_end":_date(r.get("period_end") or r.get("end"),"period_end"),"currency":(r.get("currency") or fallback).upper(),field:_number(r.get("value"),"value")});provenance[(field,year,period)]=StatementProvenance(field,doc,r.get("source_url") or r.get("url"),_confidence(r.get("confidence")),_req(r.get("accounting_standard"),"accounting_standard"),r.get("extraction_method") or "verified_export",r.get("normalization_method") or "netherlands_verified_csv",year,period)
    if not any(out.values()):raise ValueError("Netherlands facts CSV must contain statement facts.")
    return out,list(provenance.values())
def _shares(symbol,path):
    rows=_read(path)
    if len(rows)!=1:raise ValueError("Netherlands shares CSV must contain exactly one row.")
    r=rows[0];_symbol(symbol,r,"shares CSV");return CanonicalSharesOutstanding(symbol,_number(r.get("shares_outstanding") or r.get("shares"),"shares_outstanding"),_date(r.get("as_of") or r.get("date"),"as_of"),_req(r.get("source"),"source"))
def _read(path):
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(f"Netherlands verified source file does not exist: {path}")
    with path.open(newline="",encoding="utf-8") as h:return [{k:v.strip() if isinstance(v,str) else v for k,v in r.items()} for r in csv.DictReader(h)]
def _symbol(symbol,row,name):
    if row.get("symbol") and normalize_netherlands_symbol(row["symbol"])!=symbol:raise ValueError(f"{name} symbol {normalize_netherlands_symbol(row['symbol'])} does not match {symbol}.")
def _req(value,field):
    if value is None or value=="":raise ValueError(f"Netherlands source export missing required field: {field}.")
    return value
def _integer(v,f):
    try:return int(_req(v,f))
    except ValueError as e:raise ValueError(f"Netherlands source export has invalid integer field: {f}.") from e
def _number(v,f):
    try:return float(_req(v,f))
    except ValueError as e:raise ValueError(f"Netherlands source export has invalid numeric field: {f}.") from e
def _date(v,f):
    try:return date.fromisoformat(_req(v,f)).isoformat()
    except ValueError as e:raise ValueError(f"Netherlands source export has invalid ISO date field: {f}.") from e
def _confidence(v):
    v=v or "insufficient_source_evidence"
    if v not in {"regulatory_verified","issuer_verified","licensed_source_verified","cross_checked","provider_normalized_internal_only"}:raise ValueError(f"Unsupported Netherlands confidence: {v}.")
    return v
