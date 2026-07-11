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
class CanonicalFinancials:
    company: CanonicalCompany
    periods: tuple[CanonicalFiscalPeriod, ...]
    income_statement: tuple[dict, ...] = ()
    balance_sheet: tuple[dict, ...] = ()
    cash_flow: tuple[dict, ...] = ()


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
