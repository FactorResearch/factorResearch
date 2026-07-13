"""Database-backed Germany source and verified-import persistence."""

from __future__ import annotations

from typing import Any

from codes.data import db

from . import CanonicalFinancials, CanonicalSharesOutstanding
from .germany import GermanyDataSource, GermanyProviderAdapter, normalize_germany_symbol
from .germany_normalization import (
    INTERNAL_CONFIDENCE,
    PUBLIC_CONFIDENCE,
    GermanyNormalizationResult,
    build_germany_scoring_facts,
)
from .screener_projection import build_fundamental_screener_projection


class GermanyDatabaseDataSource(GermanyDataSource):
    """Read Germany canonical facts from shared market tables."""

    def get_company_profile(self, symbol): return db.get_market_company_profile("DE", normalize_germany_symbol(symbol))
    def get_financial_periods(self, symbol): return db.get_market_financial_periods("DE", normalize_germany_symbol(symbol))
    def get_income_statements(self, symbol): return db.get_market_statement_facts("DE", normalize_germany_symbol(symbol), "income")
    def get_balance_sheets(self, symbol): return db.get_market_statement_facts("DE", normalize_germany_symbol(symbol), "balance")
    def get_cash_flows(self, symbol): return db.get_market_statement_facts("DE", normalize_germany_symbol(symbol), "cash_flow")
    def get_filings(self, symbol): return self.get_source_documents(symbol)
    def get_shares_outstanding(self, symbol): return db.get_market_shares_outstanding("DE", normalize_germany_symbol(symbol))
    def get_source_documents(self, symbol): return db.get_market_source_documents("DE", normalize_germany_symbol(symbol))
    def get_statement_provenance(self, symbol): return db.get_market_statement_provenance("DE", normalize_germany_symbol(symbol))


def ingest_verified_germany_financials(symbol: str, financials: CanonicalFinancials, shares: CanonicalSharesOutstanding, *, allow_internal: bool = False) -> GermanyNormalizationResult:
    """Validate and atomically store one Germany issuer in relational tables."""
    symbol = normalize_germany_symbol(symbol)
    result = build_germany_scoring_facts(GermanyProviderAdapter(_SingleIssuerGermanySource(symbol, financials, shares)), symbol, allow_internal=allow_internal)
    if result.quality_report.confidence == INTERNAL_CONFIDENCE and not allow_internal:
        raise ValueError("Germany provider-normalized data requires allow_internal=True and cannot publish.")
    row = _public_screener_projection(result, financials)
    db.upsert_market_canonical_facts("DE", symbol, financials, shares, result.quality_report, screener_row=row)
    return result


def materialize_germany_screener_projection(symbol: str) -> bool:
    symbol = normalize_germany_symbol(symbol)
    provider = GermanyProviderAdapter(GermanyDatabaseDataSource())
    result = build_germany_scoring_facts(provider, symbol)
    if not result.can_score or result.quality_report.confidence not in PUBLIC_CONFIDENCE:
        db.delete_market_screener_row("DE", symbol)
        return False
    row = _public_screener_projection(result, provider.get_financials(symbol))
    if row is None:
        db.delete_market_screener_row("DE", symbol)
        return False
    db.upsert_market_screener_row("DE", symbol, row)
    return True


def _public_screener_projection(result: GermanyNormalizationResult, financials: CanonicalFinancials) -> dict | None:
    if not result.can_score or result.quality_report.confidence not in PUBLIC_CONFIDENCE:
        return None
    company = financials.company
    return build_fundamental_screener_projection(market_code="DE", symbol=result.symbol, name=company.name, sector=None, currency=company.currency or "EUR", sec_facts=result.sec_facts, data_confidence=result.quality_report.confidence)


class _SingleIssuerGermanySource:
    def __init__(self, symbol: str, financials: CanonicalFinancials, shares: CanonicalSharesOutstanding):
        self.symbol, self.financials, self.shares = symbol, financials, shares
    def get_company_profile(self, symbol):
        c = self.financials.company
        return {"issuer_name": c.name, "exchange": c.exchange, "country": c.country, "currency": c.currency, "regulator_id": c.regulator_id, "security_type": c.security_type, "accounting_standard": c.accounting_standard}
    def get_financial_periods(self, symbol): return [{"fiscal_year": x.fiscal_year, "fiscal_period": x.fiscal_period, "period_end": x.period_end, "currency": x.currency} for x in self.financials.periods]
    def get_income_statements(self, symbol): return list(self.financials.income_statement)
    def get_balance_sheets(self, symbol): return list(self.financials.balance_sheet)
    def get_cash_flows(self, symbol): return list(self.financials.cash_flow)
    def get_filings(self, symbol): return self.get_source_documents(symbol)
    def get_shares_outstanding(self, symbol): return {"shares_outstanding": self.shares.shares_outstanding, "as_of": self.shares.as_of, "source": self.shares.source}
    def get_source_documents(self, symbol): return [_as_dict(x) for x in self.financials.source_documents]
    def get_statement_provenance(self, symbol): return [_as_dict(x) for x in self.financials.provenance]


def _as_dict(value) -> dict[str, Any]:
    return dict(value.__dict__)
