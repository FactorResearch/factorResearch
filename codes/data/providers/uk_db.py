"""Database-backed UK data source."""

from __future__ import annotations

from typing import Any

from codes.data import db

from . import CanonicalFinancials, CanonicalSharesOutstanding
from .uk import UKDataSource, normalize_uk_symbol
from .uk_normalization import (
    INTERNAL_CONFIDENCE,
    PUBLIC_CONFIDENCE,
    UKNormalizationResult,
    build_uk_scoring_facts,
)
from .screener_projection import build_fundamental_screener_projection


class UKDatabaseDataSource(UKDataSource):
    """Read normalized UK facts from the market database."""

    def get_company_profile(self, symbol: str) -> dict[str, Any] | None:
        return db.get_market_company_profile("GB", normalize_uk_symbol(symbol))

    def get_financial_periods(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_financial_periods("GB", normalize_uk_symbol(symbol))

    def get_income_statements(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_statement_facts("GB", normalize_uk_symbol(symbol), "income")

    def get_balance_sheets(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_statement_facts("GB", normalize_uk_symbol(symbol), "balance")

    def get_cash_flows(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_statement_facts("GB", normalize_uk_symbol(symbol), "cash_flow")

    def get_filings(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_source_documents("GB", normalize_uk_symbol(symbol))

    def get_shares_outstanding(self, symbol: str) -> dict[str, Any] | None:
        return db.get_market_shares_outstanding("GB", normalize_uk_symbol(symbol))

    def get_source_documents(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_source_documents("GB", normalize_uk_symbol(symbol))

    def get_statement_provenance(self, symbol: str) -> list[dict[str, Any]]:
        return db.get_market_statement_provenance("GB", normalize_uk_symbol(symbol))


def ingest_verified_uk_financials(
    symbol: str,
    financials: CanonicalFinancials,
    shares: CanonicalSharesOutstanding,
    *,
    allow_internal: bool = False,
) -> UKNormalizationResult:
    """Validate and persist one normalized UK issuer payload.

    Public ingestion uses the same scoring gate as runtime analysis. Provider-
    normalized data can be stored only when explicitly marked internal.
    """
    from .uk import UKProviderAdapter

    normalized_symbol = normalize_uk_symbol(symbol)
    source = _SingleIssuerUKSource(normalized_symbol, financials, shares)
    provider = UKProviderAdapter(source)
    result = build_uk_scoring_facts(provider, normalized_symbol, allow_internal=allow_internal)
    if result.quality_report.confidence == INTERNAL_CONFIDENCE and not allow_internal:
        raise ValueError(
            "UK provider-normalized data requires allow_internal=True and cannot publish."
        )
    screener_row = _public_screener_projection(result, financials)
    db.upsert_market_canonical_facts(
        "GB",
        normalized_symbol,
        financials,
        shares,
        result.quality_report,
        screener_row=screener_row,
    )
    return result


def materialize_uk_screener_projection(symbol: str) -> bool:
    """Backfill a verified UK row from already-persisted canonical facts."""
    normalized_symbol = normalize_uk_symbol(symbol)
    provider = UKProviderAdapter(UKDatabaseDataSource())
    result = build_uk_scoring_facts(provider, normalized_symbol)
    if not result.can_score or result.quality_report.confidence not in PUBLIC_CONFIDENCE:
        db.delete_market_screener_row("GB", normalized_symbol)
        return False

    financials = provider.get_financials(normalized_symbol)
    row = _public_screener_projection(result, financials)
    if row is None:
        db.delete_market_screener_row("GB", normalized_symbol)
        return False
    db.upsert_market_screener_row("GB", normalized_symbol, row)
    return True


def _public_screener_projection(
    result: UKNormalizationResult,
    financials: CanonicalFinancials,
) -> dict | None:
    if not result.can_score or result.quality_report.confidence not in PUBLIC_CONFIDENCE:
        return None
    company = financials.company
    return build_fundamental_screener_projection(
        market_code="GB",
        symbol=result.symbol,
        name=company.name,
        sector=None,
        currency=company.currency or "GBP",
        sec_facts=result.sec_facts,
        data_confidence=result.quality_report.confidence,
    )


class _SingleIssuerUKSource:
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
            "regulator_id": company.regulator_id,
            "security_type": company.security_type,
            "accounting_standard": company.accounting_standard,
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
