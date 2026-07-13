"""Canada market provider adapter.

This module is intentionally source-injected. SEDAR+ exposes public issuer and
document search pages, but this adapter does not scrape those pages directly.
Production can plug in a licensed market-data feed, a SEDAR+ ingestion job, or
a curated database reader without changing analysis engines.
"""

from __future__ import annotations

from typing import Any, Protocol

from . import (
    CanonicalCompany,
    CanonicalCurrency,
    CanonicalFinancials,
    CanonicalFiscalPeriod,
    CanonicalSharesOutstanding,
    FilingDocument,
    StatementProvenance,
)


class CanadaDataSource(Protocol):
    """Source interface for Canadian issuer data."""

    def get_company_profile(self, symbol: str) -> dict[str, Any] | None:
        ...

    def get_financial_periods(self, symbol: str) -> list[dict[str, Any]]:
        ...

    def get_income_statements(self, symbol: str) -> list[dict[str, Any]]:
        ...

    def get_balance_sheets(self, symbol: str) -> list[dict[str, Any]]:
        ...

    def get_cash_flows(self, symbol: str) -> list[dict[str, Any]]:
        ...

    def get_filings(self, symbol: str) -> list[dict[str, Any]]:
        ...

    def get_shares_outstanding(self, symbol: str) -> dict[str, Any] | None:
        ...

    def get_source_documents(self, symbol: str) -> list[dict[str, Any]]:
        ...

    def get_statement_provenance(self, symbol: str) -> list[dict[str, Any]]:
        ...


class EmptyCanadaDataSource:
    """No-network default source used until a Canada feed is configured."""

    def get_company_profile(self, symbol: str) -> dict[str, Any] | None:
        return None

    def get_financial_periods(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def get_income_statements(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def get_balance_sheets(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def get_cash_flows(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def get_filings(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def get_shares_outstanding(self, symbol: str) -> dict[str, Any] | None:
        return None

    def get_source_documents(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def get_statement_provenance(self, symbol: str) -> list[dict[str, Any]]:
        return []


class CanadaProviderAdapter:
    """Normalize Canadian issuer data into provider-neutral objects."""

    provider_name = "canada"
    country = "Canada"
    default_currency = "CAD"
    supported_exchanges = ("TSX", "TSXV", "CSE", "NEO")

    def __init__(self, source: CanadaDataSource | None = None) -> None:
        self.source = source or EmptyCanadaDataSource()

    def get_company(self, symbol: str) -> CanonicalCompany:
        symbol = normalize_canada_symbol(symbol)
        profile = self.source.get_company_profile(symbol) or {}
        return CanonicalCompany(
            symbol=symbol,
            name=profile.get("name") or profile.get("issuer_name"),
            exchange=profile.get("exchange"),
            country=self.country,
            currency=profile.get("currency") or self.default_currency,
        )

    def get_financials(self, symbol: str) -> CanonicalFinancials:
        symbol = normalize_canada_symbol(symbol)
        company = self.get_company(symbol)
        return CanonicalFinancials(
            company=company,
            periods=tuple(_canonical_periods(self.source.get_financial_periods(symbol), company.currency)),
            income_statement=tuple(self.source.get_income_statements(symbol)),
            balance_sheet=tuple(self.source.get_balance_sheets(symbol)),
            cash_flow=tuple(self.source.get_cash_flows(symbol)),
            source_documents=tuple(self.get_source_documents(symbol)),
            provenance=tuple(self.get_statement_provenance(symbol)),
        )

    def get_filings(self, symbol: str) -> list[dict[str, Any]]:
        return list(self.source.get_filings(normalize_canada_symbol(symbol)))

    def get_shares(self, symbol: str) -> dict[str, Any]:
        canonical = self.get_shares_outstanding(symbol)
        return {
            "symbol": canonical.symbol,
            "shares_outstanding": canonical.shares_outstanding,
            "as_of": canonical.as_of,
            "source": canonical.source,
        }

    def get_shares_outstanding(self, symbol: str) -> CanonicalSharesOutstanding:
        symbol = normalize_canada_symbol(symbol)
        row = self.source.get_shares_outstanding(symbol) or {}
        return CanonicalSharesOutstanding(
            symbol=symbol,
            shares_outstanding=_float_or_none(row.get("shares_outstanding") or row.get("shares")),
            as_of=row.get("as_of") or row.get("date"),
            source=row.get("source"),
        )

    def get_source_documents(self, symbol: str) -> list[FilingDocument]:
        getter = getattr(self.source, "get_source_documents", None)
        rows = getter(normalize_canada_symbol(symbol)) if getter else []
        return [_filing_document(row) for row in rows]

    def get_statement_provenance(self, symbol: str) -> list[StatementProvenance]:
        getter = getattr(self.source, "get_statement_provenance", None)
        rows = getter(normalize_canada_symbol(symbol)) if getter else []
        return [_statement_provenance(row) for row in rows]

    def get_currency(self, symbol: str) -> str | None:
        return self.get_currency_info(symbol).code

    def get_currency_info(self, symbol: str) -> CanonicalCurrency:
        company = self.get_company(symbol)
        code = company.currency or self.default_currency
        return CanonicalCurrency(code=code, display_name="Canadian dollar" if code == "CAD" else None)

    def get_listing_information(self, symbol: str) -> dict[str, Any]:
        company = self.get_company(symbol)
        return {
            "symbol": company.symbol,
            "exchange": company.exchange,
            "country": company.country,
            "currency": company.currency,
            "supported_exchanges": list(self.supported_exchanges),
        }


def normalize_canada_symbol(symbol: str) -> str:
    """Normalize common Canadian ticker input without guessing listings."""
    value = str(symbol or "").upper().strip()
    if not value:
        return value
    value = value.replace(":", ".")
    if value.endswith(".TSX"):
        return value[:-4] + ".TO"
    if value.endswith(".TSXV"):
        return value[:-5] + ".V"
    return value


def is_canadian_symbol(symbol: str) -> bool:
    value = normalize_canada_symbol(symbol)
    return value.endswith((".TO", ".V", ".CN", ".NE"))


def _canonical_period(row: dict[str, Any], fallback_currency: str | None) -> CanonicalFiscalPeriod | None:
    year = _int_or_none(row.get("fiscal_year") or row.get("year"))
    period_end = row.get("period_end") or row.get("end_date")
    if year is None or not period_end:
        return None
    return CanonicalFiscalPeriod(
        fiscal_year=year,
        fiscal_period=str(row.get("fiscal_period") or row.get("period") or "FY"),
        period_end=str(period_end),
        currency=row.get("currency") or fallback_currency,
    )


def _canonical_periods(rows: list[dict[str, Any]], fallback_currency: str | None) -> list[CanonicalFiscalPeriod]:
    periods = []
    for row in rows:
        period = _canonical_period(row, fallback_currency)
        if period is not None:
            periods.append(period)
    return periods


def _filing_document(row: dict[str, Any]) -> FilingDocument:
    return FilingDocument(
        document_id=str(row.get("document_id") or row.get("id") or ""),
        source=str(row.get("source") or "unknown"),
        url=row.get("url"),
        filing_date=row.get("filing_date") or row.get("date"),
        period_end=row.get("period_end"),
        form=row.get("form") or row.get("document_type"),
        confidence=row.get("confidence") or "insufficient_source_evidence",
    )


def _statement_provenance(row: dict[str, Any]) -> StatementProvenance:
    return StatementProvenance(
        fact_name=str(row.get("fact_name") or row.get("field") or ""),
        source_document_id=str(row.get("source_document_id") or row.get("document_id") or ""),
        fiscal_year=_int_or_none(row.get("fiscal_year") or row.get("year")),
        fiscal_period=row.get("fiscal_period") or row.get("period"),
        source_url=row.get("source_url") or row.get("url"),
        confidence=row.get("confidence") or "insufficient_source_evidence",
        accounting_standard=row.get("accounting_standard"),
        extraction_method=row.get("extraction_method"),
        normalization_method=row.get("normalization_method"),
    )


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
