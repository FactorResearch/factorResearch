"""Provider adapter contracts for normalized data access.

Business logic should depend on these provider-neutral protocols and canonical
objects, not on vendor payloads or HTTP clients.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CanonicalCompany:
    symbol: str
    name: str | None = None
    exchange: str | None = None
    country: str | None = None
    currency: str | None = None


@dataclass(frozen=True)
class CanonicalFiscalPeriod:
    fiscal_year: int
    fiscal_period: str
    period_end: str
    currency: str | None = None


@dataclass(frozen=True)
class CanonicalSharesOutstanding:
    symbol: str
    shares_outstanding: float | None
    as_of: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class CanonicalCurrency:
    code: str
    display_name: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class FilingDocument:
    document_id: str
    source: str
    url: str | None = None
    filing_date: str | None = None
    period_end: str | None = None
    form: str | None = None
    confidence: str = "insufficient_source_evidence"


@dataclass(frozen=True)
class StatementProvenance:
    fact_name: str
    source_document_id: str
    source_url: str | None = None
    confidence: str = "insufficient_source_evidence"
    accounting_standard: str | None = None
    extraction_method: str | None = None
    normalization_method: str | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None


@dataclass(frozen=True)
class DataQualityIssue:
    code: str
    message: str
    severity: str = "error"
    field: str | None = None


@dataclass(frozen=True)
class DataQualityReport:
    market: str
    can_score: bool
    confidence: str
    issues: tuple[DataQualityIssue, ...] = ()


@dataclass(frozen=True)
class CanonicalFinancials:
    company: CanonicalCompany
    periods: tuple[CanonicalFiscalPeriod, ...]
    income_statement: tuple[dict, ...] = ()
    balance_sheet: tuple[dict, ...] = ()
    cash_flow: tuple[dict, ...] = ()
    source_documents: tuple[FilingDocument, ...] = ()
    provenance: tuple[StatementProvenance, ...] = ()


class MarketProviderAdapter(Protocol):
    """Protocol every market/provider adapter must implement."""

    provider_name: str

    def get_company(self, symbol: str) -> CanonicalCompany:
        ...

    def get_financials(self, symbol: str) -> CanonicalFinancials:
        ...

    def get_filings(self, symbol: str) -> list[dict]:
        ...

    def get_shares(self, symbol: str) -> dict:
        ...

    def get_currency(self, symbol: str) -> str | None:
        ...

    def get_listing_information(self, symbol: str) -> dict:
        ...
