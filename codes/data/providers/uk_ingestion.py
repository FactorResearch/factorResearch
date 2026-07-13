"""Verified UK source-export ingestion.

This module owns the boundary between source extraction and normalized UK
storage. It accepts structured exports from a verified extraction process and
converts them to canonical provider objects before DB persistence.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from . import (
    CanonicalCompany,
    CanonicalFinancials,
    CanonicalFiscalPeriod,
    CanonicalSharesOutstanding,
    FilingDocument,
    StatementProvenance,
)
from .uk import normalize_uk_symbol
from .uk_db import ingest_verified_uk_financials
from .uk_normalization import UKNormalizationResult


STATEMENT_TYPES = {"income", "balance", "cash_flow"}
PACKAGE_CONFIDENCE = {
    "regulatory_verified",
    "issuer_verified",
    "licensed_source_verified",
    "cross_checked",
    "provider_normalized_internal_only",
}


@dataclass(frozen=True)
class UKVerifiedCsvBundle:
    company_csv: Path
    periods_csv: Path
    documents_csv: Path
    facts_csv: Path
    shares_csv: Path


def import_uk_verified_csv_bundle(
    symbol: str,
    bundle: UKVerifiedCsvBundle,
    *,
    allow_internal: bool = False,
) -> UKNormalizationResult:
    """Load a verified CSV export bundle, validate, and persist to DB."""
    normalized_symbol = normalize_uk_symbol(symbol)
    financials, shares = load_uk_verified_csv_bundle(normalized_symbol, bundle)
    return ingest_verified_uk_financials(
        normalized_symbol,
        financials,
        shares,
        allow_internal=allow_internal,
    )


def load_uk_verified_csv_bundle(
    symbol: str,
    bundle: UKVerifiedCsvBundle,
) -> tuple[CanonicalFinancials, CanonicalSharesOutstanding]:
    normalized_symbol = normalize_uk_symbol(symbol)
    company = _load_company(normalized_symbol, bundle.company_csv)
    periods = tuple(_load_periods(normalized_symbol, bundle.periods_csv, company.currency))
    documents = tuple(_load_documents(bundle.documents_csv))
    income, balance, cash_flow, provenance = _load_facts(
        normalized_symbol,
        bundle.facts_csv,
        periods,
        documents,
        company.currency,
    )
    shares = _load_shares(normalized_symbol, bundle.shares_csv)
    return (
        CanonicalFinancials(
            company=company,
            periods=periods,
            income_statement=tuple(income),
            balance_sheet=tuple(balance),
            cash_flow=tuple(cash_flow),
            source_documents=documents,
            provenance=tuple(provenance),
        ),
        shares,
    )


def _load_company(symbol: str, path: Path) -> CanonicalCompany:
    rows = _read_csv(path)
    if len(rows) != 1:
        raise ValueError("UK company CSV must contain exactly one row.")
    row = rows[0]
    row_symbol = normalize_uk_symbol(row.get("symbol") or symbol)
    if row_symbol != symbol:
        raise ValueError(f"Company CSV symbol {row_symbol} does not match requested symbol {symbol}.")
    currency = (row.get("currency") or "GBP").upper()
    if not currency:
        raise ValueError("UK company CSV requires currency.")
    return CanonicalCompany(
        symbol=symbol,
        name=row.get("name") or row.get("issuer_name"),
        exchange=row.get("exchange"),
        country=row.get("country") or "United Kingdom",
        currency=currency,
        regulator_id=_required(
            row.get("regulator_id") or row.get("company_number") or row.get("lei"),
            "regulator_id",
        ),
        security_type=_required(row.get("security_type"), "security_type").lower(),
        accounting_standard=_required(row.get("accounting_standard"), "accounting_standard"),
    )


def _load_periods(symbol: str, path: Path, fallback_currency: str | None) -> list[CanonicalFiscalPeriod]:
    periods = []
    seen = set()
    for row in _read_csv(path):
        _assert_symbol(symbol, row, "periods CSV")
        year = _int_required(row.get("fiscal_year") or row.get("year"), "fiscal_year")
        period_end = _date_required(row.get("period_end"), "period_end")
        fiscal_period = row.get("fiscal_period") or row.get("period") or "FY"
        key = (year, fiscal_period)
        if key in seen:
            raise ValueError(f"UK periods CSV has duplicate fiscal period: {year} {fiscal_period}.")
        seen.add(key)
        periods.append(CanonicalFiscalPeriod(
            fiscal_year=year,
            fiscal_period=fiscal_period,
            period_end=period_end,
            currency=(row.get("currency") or fallback_currency or "GBP").upper(),
        ))
    if not periods:
        raise ValueError("UK periods CSV must contain at least one period.")
    return periods


def _load_documents(path: Path) -> list[FilingDocument]:
    documents = []
    seen = set()
    for row in _read_csv(path):
        confidence = _confidence(row.get("confidence"))
        document_id = _required(row.get("document_id") or row.get("id"), "document_id")
        if document_id in seen:
            raise ValueError(f"UK documents CSV has duplicate document_id: {document_id}.")
        seen.add(document_id)
        documents.append(FilingDocument(
            document_id=document_id,
            source=_required(row.get("source"), "source"),
            url=row.get("url") or None,
            filing_date=_date_required(row.get("filing_date") or row.get("date"), "filing_date"),
            period_end=_date_required(row.get("period_end"), "period_end"),
            form=row.get("form") or row.get("document_type") or None,
            confidence=confidence,
        ))
    if not documents:
        raise ValueError("UK documents CSV must contain at least one source document.")
    return documents


def _load_facts(
    symbol: str,
    path: Path,
    periods: tuple[CanonicalFiscalPeriod, ...],
    documents: tuple[FilingDocument, ...],
    fallback_currency: str | None,
) -> tuple[list[dict], list[dict], list[dict], list[StatementProvenance]]:
    document_ids = {document.document_id for document in documents}
    period_map = {
        (period.fiscal_year, period.fiscal_period): period.period_end
        for period in periods
    }
    grouped: dict[tuple[str, int, str], dict] = {}
    provenance_by_fact_period: dict[tuple[str, int, str], StatementProvenance] = {}
    seen_facts = set()

    for row in _read_csv(path):
        _assert_symbol(symbol, row, "facts CSV")
        statement_type = _required(row.get("statement_type"), "statement_type")
        if statement_type not in STATEMENT_TYPES:
            raise ValueError(f"Unsupported UK statement_type: {statement_type}.")
        fact_name = _required(row.get("fact_name"), "fact_name")
        fiscal_year = _int_required(row.get("fiscal_year") or row.get("year"), "fiscal_year")
        fiscal_period = row.get("fiscal_period") or row.get("period") or "FY"
        period_key = (fiscal_year, fiscal_period)
        if period_key not in period_map:
            raise ValueError(f"Fact {fact_name} references unknown fiscal period {fiscal_year} {fiscal_period}.")
        fact_key = (fact_name, fiscal_year, fiscal_period)
        if fact_key in seen_facts:
            raise ValueError(f"UK facts CSV has duplicate fact: {fact_name} {fiscal_year} {fiscal_period}.")
        seen_facts.add(fact_key)
        period_end = _date_required(row.get("period_end"), "period_end")
        if period_end != period_map[period_key]:
            raise ValueError(
                f"Fact {fact_name} period_end {period_end} does not match "
                f"declared period {period_map[period_key]}."
            )
        document_id = _required(row.get("source_document_id") or row.get("document_id"), "source_document_id")
        if document_id not in document_ids:
            raise ValueError(f"Fact {fact_name} references unknown source document {document_id}.")

        key = (statement_type, fiscal_year, fiscal_period)
        item = grouped.setdefault(key, {
            "fiscal_year": fiscal_year,
            "fiscal_period": fiscal_period,
            "period_end": period_end,
            "currency": (row.get("currency") or fallback_currency or "GBP").upper(),
        })
        item[fact_name] = _float_required(row.get("value"), f"value for {fact_name}")
        provenance_by_fact_period.setdefault((fact_name, fiscal_year, fiscal_period), StatementProvenance(
            fact_name=fact_name,
            source_document_id=document_id,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            source_url=row.get("source_url") or row.get("url") or None,
            confidence=_confidence(row.get("confidence")),
            accounting_standard=_required(row.get("accounting_standard"), "accounting_standard"),
            extraction_method=row.get("extraction_method") or None,
            normalization_method=row.get("normalization_method") or "uk_verified_csv",
        ))

    statements = {"income": [], "balance": [], "cash_flow": []}
    for (statement_type, _year, _period), row in grouped.items():
        statements[statement_type].append(row)
    if not any(statements.values()):
        raise ValueError("UK facts CSV must contain statement facts.")
    return (
        _sort_statement_rows(statements["income"]),
        _sort_statement_rows(statements["balance"]),
        _sort_statement_rows(statements["cash_flow"]),
        list(provenance_by_fact_period.values()),
    )


def _load_shares(symbol: str, path: Path) -> CanonicalSharesOutstanding:
    rows = _read_csv(path)
    if len(rows) != 1:
        raise ValueError("UK shares CSV must contain exactly one row.")
    row = rows[0]
    _assert_symbol(symbol, row, "shares CSV")
    return CanonicalSharesOutstanding(
        symbol=symbol,
        shares_outstanding=_float_required(row.get("shares_outstanding") or row.get("shares"), "shares_outstanding"),
        as_of=_date_required(row.get("as_of") or row.get("date"), "as_of"),
        source=_required(row.get("source"), "source"),
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"UK verified source file does not exist: {source}")
    with source.open(newline="", encoding="utf-8") as handle:
        return [{key: (value.strip() if isinstance(value, str) else value) for key, value in row.items()}
                for row in csv.DictReader(handle)]


def _sort_statement_rows(rows: Iterable[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: (row.get("fiscal_year") or 0, row.get("fiscal_period") or ""), reverse=True)


def _assert_symbol(symbol: str, row: dict, source_name: str) -> None:
    row_symbol = row.get("symbol")
    if row_symbol and normalize_uk_symbol(row_symbol) != symbol:
        raise ValueError(f"{source_name} symbol {normalize_uk_symbol(row_symbol)} does not match {symbol}.")


def _confidence(value: str | None) -> str:
    confidence = value or "insufficient_source_evidence"
    if confidence not in PACKAGE_CONFIDENCE:
        raise ValueError(f"Unsupported UK confidence: {confidence}.")
    return confidence


def _required(value: str | None, field_name: str) -> str:
    if value is None or value == "":
        raise ValueError(f"UK source export missing required field: {field_name}.")
    return value


def _int_required(value: str | int | None, field_name: str) -> int:
    try:
        return int(_required(str(value) if value is not None else None, field_name))
    except ValueError as exc:
        raise ValueError(f"UK source export has invalid integer field: {field_name}.") from exc


def _float_required(value: str | float | None, field_name: str) -> float:
    try:
        return float(_required(str(value) if value is not None else None, field_name))
    except ValueError as exc:
        raise ValueError(f"UK source export has invalid numeric field: {field_name}.") from exc


def _date_required(value: str | None, field_name: str) -> str:
    raw = _required(value, field_name)
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"UK source export has invalid ISO date field: {field_name}."
        ) from exc
