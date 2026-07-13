"""Germany market provider adapter.

Source acquisition stays outside the web app. Production may inject verified
Bundesanzeiger, Unternehmensregister, BaFin, Deutsche Boerse, issuer, or
licensed-source data without exposing source payloads to analysis engines.
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


class GermanyDataSource(Protocol):
    def get_company_profile(self, symbol: str) -> dict[str, Any] | None: ...
    def get_financial_periods(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_income_statements(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_balance_sheets(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_cash_flows(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_filings(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_shares_outstanding(self, symbol: str) -> dict[str, Any] | None: ...
    def get_source_documents(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_statement_provenance(self, symbol: str) -> list[dict[str, Any]]: ...


class EmptyGermanyDataSource:
    """No-network default source until an approved Germany feed is configured."""

    def get_company_profile(self, symbol: str): return None
    def get_financial_periods(self, symbol: str): return []
    def get_income_statements(self, symbol: str): return []
    def get_balance_sheets(self, symbol: str): return []
    def get_cash_flows(self, symbol: str): return []
    def get_filings(self, symbol: str): return []
    def get_shares_outstanding(self, symbol: str): return None
    def get_source_documents(self, symbol: str): return []
    def get_statement_provenance(self, symbol: str): return []


class GermanyProviderAdapter:
    provider_name = "germany"
    country = "Germany"
    default_currency = "EUR"
    supported_exchanges = ("XETRA", "FRA", "GETTEX", "STUTTGART")

    def __init__(self, source: GermanyDataSource | None = None) -> None:
        self.source = source or EmptyGermanyDataSource()

    def get_company(self, symbol: str) -> CanonicalCompany:
        symbol = normalize_germany_symbol(symbol)
        profile = self.source.get_company_profile(symbol) or {}
        return CanonicalCompany(
            symbol=symbol, name=profile.get("name") or profile.get("issuer_name"),
            exchange=profile.get("exchange"), country=self.country,
            currency=profile.get("currency") or self.default_currency,
            regulator_id=profile.get("regulator_id") or profile.get("lei") or profile.get("register_number"),
            security_type=profile.get("security_type"), accounting_standard=profile.get("accounting_standard"),
        )

    def get_financials(self, symbol: str) -> CanonicalFinancials:
        symbol = normalize_germany_symbol(symbol)
        company = self.get_company(symbol)
        return CanonicalFinancials(
            company=company,
            periods=tuple(_period(row, company.currency) for row in self.source.get_financial_periods(symbol) if _period(row, company.currency)),
            income_statement=tuple(self.source.get_income_statements(symbol)),
            balance_sheet=tuple(self.source.get_balance_sheets(symbol)),
            cash_flow=tuple(self.source.get_cash_flows(symbol)),
            source_documents=tuple(self.get_source_documents(symbol)),
            provenance=tuple(self.get_statement_provenance(symbol)),
        )

    def get_filings(self, symbol: str) -> list[dict[str, Any]]:
        return list(self.source.get_filings(normalize_germany_symbol(symbol)))

    def get_shares_outstanding(self, symbol: str) -> CanonicalSharesOutstanding:
        symbol = normalize_germany_symbol(symbol)
        row = self.source.get_shares_outstanding(symbol) or {}
        return CanonicalSharesOutstanding(symbol, _float(row.get("shares_outstanding") or row.get("shares")), row.get("as_of") or row.get("date"), row.get("source"))

    def get_shares(self, symbol: str) -> dict[str, Any]:
        value = self.get_shares_outstanding(symbol)
        return {"symbol": value.symbol, "shares_outstanding": value.shares_outstanding, "as_of": value.as_of, "source": value.source}

    def get_source_documents(self, symbol: str) -> list[FilingDocument]:
        return [_document(row) for row in self.source.get_source_documents(normalize_germany_symbol(symbol))]

    def get_statement_provenance(self, symbol: str) -> list[StatementProvenance]:
        return [_provenance(row) for row in self.source.get_statement_provenance(normalize_germany_symbol(symbol))]

    def get_currency(self, symbol: str) -> str | None:
        return self.get_company(symbol).currency

    def get_currency_info(self, symbol: str) -> CanonicalCurrency:
        return CanonicalCurrency(self.get_currency(symbol) or self.default_currency, "Euro")

    def get_listing_information(self, symbol: str) -> dict[str, Any]:
        company = self.get_company(symbol)
        return {"symbol": company.symbol, "exchange": company.exchange, "country": company.country, "currency": company.currency, "regulator_id": company.regulator_id, "security_type": company.security_type, "accounting_standard": company.accounting_standard, "supported_exchanges": list(self.supported_exchanges)}


def normalize_germany_symbol(symbol: str) -> str:
    """Normalize explicit Deutsche Boerse exchange notation without guessing."""
    value = str(symbol or "").upper().strip().replace(":", ".")
    return value[:-6] + ".DE" if value.endswith(".XETRA") else value


def is_germany_symbol(symbol: str) -> bool:
    return normalize_germany_symbol(symbol).endswith((".DE", ".F"))


def _period(row: dict[str, Any], fallback: str | None) -> CanonicalFiscalPeriod | None:
    try:
        year = int(row.get("fiscal_year") or row.get("year"))
    except (TypeError, ValueError):
        return None
    end = row.get("period_end") or row.get("end_date")
    return CanonicalFiscalPeriod(year, str(row.get("fiscal_period") or row.get("period") or "FY"), str(end), row.get("currency") or fallback) if end else None


def _document(row: dict[str, Any]) -> FilingDocument:
    return FilingDocument(str(row.get("document_id") or row.get("id") or ""), str(row.get("source") or "unknown"), row.get("url"), row.get("filing_date") or row.get("date"), row.get("period_end"), row.get("form") or row.get("document_type"), row.get("confidence") or "insufficient_source_evidence")


def _provenance(row: dict[str, Any]) -> StatementProvenance:
    try: year = int(row.get("fiscal_year") or row.get("year"))
    except (TypeError, ValueError): year = None
    return StatementProvenance(str(row.get("fact_name") or row.get("field") or ""), str(row.get("source_document_id") or row.get("document_id") or ""), row.get("source_url") or row.get("url"), row.get("confidence") or "insufficient_source_evidence", row.get("accounting_standard"), row.get("extraction_method"), row.get("normalization_method"), year, row.get("fiscal_period") or row.get("period"))


def _float(value) -> float | None:
    try: return float(value)
    except (TypeError, ValueError): return None
