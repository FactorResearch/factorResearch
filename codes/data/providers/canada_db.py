"""Database-backed Canada data source."""

from __future__ import annotations

from typing import Any

from codes.data import db

from . import CanonicalFinancials, CanonicalSharesOutstanding
from .canada import CanadaDataSource, normalize_canada_symbol
from .canada_normalization import CanadaNormalizationResult, build_canada_scoring_facts


class CanadaDatabaseDataSource(CanadaDataSource):
    """Read normalized Canada facts from the market database."""

    def get_company_profile(self, symbol: str) -> dict[str, Any] | None:
        return db.get_canada_company_profile(normalize_canada_symbol(symbol))

    def get_financial_periods(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_canada_financial_periods(normalize_canada_symbol(symbol))

    def get_income_statements(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_canada_statement_facts(normalize_canada_symbol(symbol), "income")

    def get_balance_sheets(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_canada_statement_facts(normalize_canada_symbol(symbol), "balance")

    def get_cash_flows(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_canada_statement_facts(normalize_canada_symbol(symbol), "cash_flow")

    def get_filings(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_canada_filings(normalize_canada_symbol(symbol))

    def get_shares_outstanding(self, symbol: str) -> dict[str, Any] | None:
        return db.get_canada_shares_outstanding(normalize_canada_symbol(symbol))

    def get_source_documents(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_canada_source_documents(normalize_canada_symbol(symbol))

    def get_statement_provenance(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_canada_statement_provenance(normalize_canada_symbol(symbol))


def ingest_verified_canada_financials(
    symbol: str,
    financials: CanonicalFinancials,
    shares: CanonicalSharesOutstanding,
    *,
    allow_internal: bool = False,
) -> CanadaNormalizationResult:
    """Validate and persist one normalized Canada issuer payload.

    Public ingestion uses the same scoring gate as runtime analysis. Provider-
    normalized data can be stored only when explicitly marked internal.
    """
    from .canada import CanadaProviderAdapter

    normalized_symbol = normalize_canada_symbol(symbol)
    source = _SingleIssuerCanadaSource(normalized_symbol, financials, shares)
    provider = CanadaProviderAdapter(source)
    result = build_canada_scoring_facts(provider, normalized_symbol, allow_internal=allow_internal)
    db.upsert_canada_canonical_facts(
        normalized_symbol,
        financials,
        shares,
        result.quality_report,
    )
    return result


class _SingleIssuerCanadaSource:
    def __init__(
        self,
        symbol: str,
        financials: CanonicalFinancials,
        shares: CanonicalSharesOutstanding,
    ) -> None:
        self.symbol = symbol
        self.financials = financials
        self.shares = shares

    def get_company_profile(self, symbol: str) -> dict[str, Any] | None:
        company = self.financials.company
        return {
            "issuer_name": company.name,
            "exchange": company.exchange,
            "country": company.country,
            "currency": company.currency,
        }

    def get_financial_periods(self, symbol: str) -> list[dict[str, Any]]:
        return [{
            "fiscal_year": period.fiscal_year,
            "fiscal_period": period.fiscal_period,
            "period_end": period.period_end,
            "currency": period.currency,
        } for period in self.financials.periods]

    def get_income_statements(self, symbol: str) -> list[dict[str, Any]]:
        return list(self.financials.income_statement)

    def get_balance_sheets(self, symbol: str) -> list[dict[str, Any]]:
        return list(self.financials.balance_sheet)

    def get_cash_flows(self, symbol: str) -> list[dict[str, Any]]:
        return list(self.financials.cash_flow)

    def get_filings(self, symbol: str) -> list[dict[str, Any]]:
        return self.get_source_documents(symbol)

    def get_shares_outstanding(self, symbol: str) -> dict[str, Any] | None:
        return {
            "shares_outstanding": self.shares.shares_outstanding,
            "as_of": self.shares.as_of,
            "source": self.shares.source,
        }

    def get_source_documents(self, symbol: str) -> list[dict[str, Any]]:
        return [_dataclass_dict(document) for document in self.financials.source_documents]

    def get_statement_provenance(self, symbol: str) -> list[dict[str, Any]]:
        return [_dataclass_dict(item) for item in self.financials.provenance]


def _dataclass_dict(value) -> dict[str, Any]:
    return dict(value.__dict__)
