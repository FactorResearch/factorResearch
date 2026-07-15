"""Database-backed Canada data source."""

from __future__ import annotations

from typing import Any

from codes.data import db

from . import CanonicalFinancials, CanonicalSharesOutstanding
from .canada import CanadaDataSource, normalize_canada_symbol
from .canada_normalization import (
    PUBLIC_CONFIDENCE,
    CanadaNormalizationResult,
    build_canada_scoring_facts,
)
from .screener_projection import build_fundamental_screener_projection


class CanadaDatabaseDataSource(CanadaDataSource):
    """Read normalized Canada facts from the market database."""

    def get_company_profile(self, symbol: str) -> dict[str, Any] | None:
        return db.get_market_company_profile("CA", normalize_canada_symbol(symbol))

    def get_financial_periods(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_financial_periods("CA", normalize_canada_symbol(symbol))

    def get_income_statements(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_statement_facts("CA", normalize_canada_symbol(symbol), "income")

    def get_balance_sheets(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_statement_facts("CA", normalize_canada_symbol(symbol), "balance")

    def get_cash_flows(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_statement_facts("CA", normalize_canada_symbol(symbol), "cash_flow")

    def get_filings(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_source_documents("CA", normalize_canada_symbol(symbol))

    def get_shares_outstanding(self, symbol: str) -> dict[str, Any] | None:
        return db.get_market_shares_outstanding("CA", normalize_canada_symbol(symbol))

    def get_source_documents(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_source_documents("CA", normalize_canada_symbol(symbol))

    def get_statement_provenance(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_statement_provenance("CA", normalize_canada_symbol(symbol))


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
    screener_row = _public_screener_projection(result, financials)
    db.upsert_market_canonical_facts(
        "CA",
        normalized_symbol,
        financials,
        shares,
        result.quality_report,
        screener_row=screener_row,
    )
    return result


def materialize_canada_screener_projection(symbol: str) -> bool:
    """Backfill a verified Canada row from already-persisted canonical facts."""
    normalized_symbol = normalize_canada_symbol(symbol)
    provider = CanadaProviderAdapter(CanadaDatabaseDataSource())
    result = build_canada_scoring_facts(provider, normalized_symbol)
    if not result.can_score or result.quality_report.confidence not in PUBLIC_CONFIDENCE:
        db.delete_market_screener_row("CA", normalized_symbol)
        return False

    financials = provider.get_financials(normalized_symbol)
    row = _public_screener_projection(result, financials)
    if row is None:
        db.delete_market_screener_row("CA", normalized_symbol)
        return False
    db.upsert_market_screener_row("CA", normalized_symbol, row)
    return True


def _public_screener_projection(
    result: CanadaNormalizationResult,
    financials: CanonicalFinancials,
) -> dict | None:
    if not result.can_score or result.quality_report.confidence not in PUBLIC_CONFIDENCE:
        return None
    company = financials.company
    return build_fundamental_screener_projection(
        market_code="CA",
        symbol=result.symbol,
        name=company.name,
        sector=None,
        currency=company.currency or "CAD",
        sec_facts=result.sec_facts,
        data_confidence=result.quality_report.confidence,
    )


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
