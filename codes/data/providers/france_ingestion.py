"""Verified France CSV import. Durable data is written only to PostgreSQL."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import CanonicalCompany, CanonicalFinancials, CanonicalFiscalPeriod, CanonicalSharesOutstanding, FilingDocument, StatementProvenance
from .france import normalize_france_symbol
from .france_db import ingest_verified_france_financials
from .france_normalization import FranceNormalizationResult

STATEMENT_TYPES = {"income", "balance", "cash_flow"}
PACKAGE_CONFIDENCE = {"regulatory_verified", "issuer_verified", "licensed_source_verified", "cross_checked", "provider_normalized_internal_only"}


@dataclass(frozen=True)
class FranceVerifiedCsvBundle:
    company_csv: Path
    periods_csv: Path
    documents_csv: Path
    facts_csv: Path
    shares_csv: Path


def import_france_verified_csv_bundle(symbol: str, bundle: FranceVerifiedCsvBundle, *, allow_internal: bool = False) -> FranceNormalizationResult:
    financials, shares = load_france_verified_csv_bundle(symbol, bundle)
    return ingest_verified_france_financials(symbol, financials, shares, allow_internal=allow_internal)


def load_france_verified_csv_bundle(symbol: str, bundle: FranceVerifiedCsvBundle) -> tuple[CanonicalFinancials, CanonicalSharesOutstanding]:
    symbol = normalize_france_symbol(symbol); company = _company(symbol, bundle.company_csv)
    periods = tuple(_periods(symbol, bundle.periods_csv, company.currency)); documents = tuple(_documents(bundle.documents_csv))
    statements, provenance = _facts(symbol, bundle.facts_csv, periods, documents, company.currency)
    return CanonicalFinancials(company, periods, tuple(statements["income"]), tuple(statements["balance"]), tuple(statements["cash_flow"]), documents, tuple(provenance)), _shares(symbol, bundle.shares_csv)


def _company(symbol, path):
    rows = _read(path)
    if len(rows) != 1: raise ValueError("France company CSV must contain exactly one row.")
    row = rows[0]; _symbol(symbol, row, "company CSV")
    return CanonicalCompany(symbol, row.get("name") or row.get("issuer_name"), row.get("exchange"), row.get("country") or "France", (row.get("currency") or "EUR").upper(), _required(row.get("regulator_id") or row.get("lei") or row.get("amf_id"), "regulator_id"), _required(row.get("security_type"), "security_type").lower(), _required(row.get("accounting_standard"), "accounting_standard"))
def _periods(symbol, path, fallback):
    result, seen = [], set()
    for row in _read(path):
        _symbol(symbol, row, "periods CSV"); item = CanonicalFiscalPeriod(_integer(row.get("fiscal_year") or row.get("year"), "fiscal_year"), (row.get("fiscal_period") or row.get("period") or "FY").upper(), _date(row.get("period_end") or row.get("end_date"), "period_end"), (row.get("currency") or fallback or "").upper())
        key = (item.fiscal_year, item.fiscal_period, item.period_end)
        if key in seen: raise ValueError(f"France periods CSV repeats fiscal period {key}.")
        seen.add(key); result.append(item)
    if not result: raise ValueError("France periods CSV must contain at least one period.")
    return sorted(result, key=lambda item: (item.fiscal_year, item.period_end), reverse=True)
def _documents(path):
    result, identifiers = [], set()
    for row in _read(path):
        identifier = _required(row.get("document_id") or row.get("id"), "document_id")
        if identifier in identifiers: raise ValueError(f"France documents CSV repeats document_id {identifier}.")
        identifiers.add(identifier); result.append(FilingDocument(identifier, _required(row.get("source"), "source"), row.get("url"), _date(row.get("filing_date") or row.get("date"), "filing_date"), row.get("period_end"), row.get("form") or row.get("document_type"), _confidence(row.get("confidence"))))
    if not result: raise ValueError("France documents CSV must contain at least one source document.")
    return result
def _facts(symbol, path, periods, documents, fallback):
    statements, provenance = {kind: [] for kind in STATEMENT_TYPES}, {}; document_ids = {item.document_id for item in documents}; period_keys = {(item.fiscal_year, item.fiscal_period) for item in periods}
    for row in _read(path):
        _symbol(symbol, row, "facts CSV"); statement = (row.get("statement_type") or "").lower()
        if statement not in STATEMENT_TYPES: raise ValueError(f"Unsupported France statement_type: {statement}.")
        field = _required(row.get("fact_name") or row.get("field"), "fact_name"); year, fiscal_period = _integer(row.get("fiscal_year") or row.get("year"), "fiscal_year"), (row.get("fiscal_period") or row.get("period") or "FY").upper()
        if (year, fiscal_period) not in period_keys: raise ValueError(f"France fact {field} refers to an unknown fiscal period.")
        document_id = _required(row.get("source_document_id") or row.get("document_id"), "source_document_id")
        if document_id not in document_ids: raise ValueError(f"France fact {field} references unknown document {document_id}.")
        statements[statement].append({"fiscal_year": year, "fiscal_period": fiscal_period, "period_end": _date(row.get("period_end") or row.get("end"), "period_end"), "currency": (row.get("currency") or fallback or "").upper(), field: _number(row.get("value"), "value")})
        provenance[(field, year, fiscal_period)] = StatementProvenance(field, document_id, row.get("source_url") or row.get("url"), _confidence(row.get("confidence")), _required(row.get("accounting_standard"), "accounting_standard"), row.get("extraction_method") or "verified_export", row.get("normalization_method") or "france_verified_csv", year, fiscal_period)
    if not any(statements.values()): raise ValueError("France facts CSV must contain statement facts.")
    return ({key: sorted(value, key=lambda item: (item["fiscal_year"], item["period_end"]), reverse=True) for key, value in statements.items()}, list(provenance.values()))
def _shares(symbol, path):
    rows = _read(path)
    if len(rows) != 1: raise ValueError("France shares CSV must contain exactly one row.")
    row = rows[0]; _symbol(symbol, row, "shares CSV")
    return CanonicalSharesOutstanding(symbol, _number(row.get("shares_outstanding") or row.get("shares"), "shares_outstanding"), _date(row.get("as_of") or row.get("date"), "as_of"), _required(row.get("source"), "source"))
def _read(path):
    path = Path(path)
    if not path.is_file(): raise FileNotFoundError(f"France verified source file does not exist: {path}")
    with path.open(newline="", encoding="utf-8") as handle: return [{key: value.strip() if isinstance(value, str) else value for key, value in row.items()} for row in csv.DictReader(handle)]
def _symbol(symbol, row, name):
    value = row.get("symbol")
    if value and normalize_france_symbol(value) != symbol: raise ValueError(f"{name} symbol {normalize_france_symbol(value)} does not match {symbol}.")
def _required(value, field):
    if value is None or value == "": raise ValueError(f"France source export missing required field: {field}.")
    return value
def _integer(value, field):
    try: return int(_required(value, field))
    except ValueError as exc: raise ValueError(f"France source export has invalid integer field: {field}.") from exc
def _number(value, field):
    try: return float(_required(value, field))
    except ValueError as exc: raise ValueError(f"France source export has invalid numeric field: {field}.") from exc
def _date(value, field):
    try: return date.fromisoformat(_required(value, field)).isoformat()
    except ValueError as exc: raise ValueError(f"France source export has invalid ISO date field: {field}.") from exc
def _confidence(value):
    value = value or "insufficient_source_evidence"
    if value not in PACKAGE_CONFIDENCE: raise ValueError(f"Unsupported France confidence: {value}.")
    return value
