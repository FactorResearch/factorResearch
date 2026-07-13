"""Relational persistence and screener projection for France facts."""

from __future__ import annotations

from typing import Any

from codes.data import db

from . import CanonicalFinancials, CanonicalSharesOutstanding
from .france import FranceDataSource, FranceProviderAdapter, normalize_france_symbol
from .france_normalization import INTERNAL_CONFIDENCE, PUBLIC_CONFIDENCE, FranceNormalizationResult, build_france_scoring_facts
from .screener_projection import build_fundamental_screener_projection


class FranceDatabaseDataSource(FranceDataSource):
    """Read France canonical facts from shared typed market tables."""
    def get_company_profile(self, symbol): return db.get_market_company_profile("FR", normalize_france_symbol(symbol))
    def get_financial_periods(self, symbol): return db.get_market_financial_periods("FR", normalize_france_symbol(symbol))
    def get_income_statements(self, symbol): return db.get_market_statement_facts("FR", normalize_france_symbol(symbol), "income")
    def get_balance_sheets(self, symbol): return db.get_market_statement_facts("FR", normalize_france_symbol(symbol), "balance")
    def get_cash_flows(self, symbol): return db.get_market_statement_facts("FR", normalize_france_symbol(symbol), "cash_flow")
    def get_filings(self, symbol): return self.get_source_documents(symbol)
    def get_shares_outstanding(self, symbol): return db.get_market_shares_outstanding("FR", normalize_france_symbol(symbol))
    def get_source_documents(self, symbol): return db.get_market_source_documents("FR", normalize_france_symbol(symbol))
    def get_statement_provenance(self, symbol): return db.get_market_statement_provenance("FR", normalize_france_symbol(symbol))


def ingest_verified_france_financials(symbol: str, financials: CanonicalFinancials, shares: CanonicalSharesOutstanding, *, allow_internal: bool = False) -> FranceNormalizationResult:
    symbol = normalize_france_symbol(symbol)
    result = build_france_scoring_facts(FranceProviderAdapter(_SingleIssuerFranceSource(symbol, financials, shares)), symbol, allow_internal=allow_internal)
    if result.quality_report.confidence == INTERNAL_CONFIDENCE and not allow_internal:
        raise ValueError("France provider-normalized data requires allow_internal=True and cannot publish.")
    row = _public_screener_projection(result, financials)
    db.upsert_market_canonical_facts("FR", symbol, financials, shares, result.quality_report, screener_row=row)
    return result


def materialize_france_screener_projection(symbol: str) -> bool:
    symbol = normalize_france_symbol(symbol)
    provider = FranceProviderAdapter(FranceDatabaseDataSource())
    result = build_france_scoring_facts(provider, symbol)
    if not result.can_score or result.quality_report.confidence not in PUBLIC_CONFIDENCE:
        db.delete_market_screener_row("FR", symbol); return False
    row = _public_screener_projection(result, provider.get_financials(symbol))
    if row is None: db.delete_market_screener_row("FR", symbol); return False
    db.upsert_market_screener_row("FR", symbol, row); return True


def _public_screener_projection(result: FranceNormalizationResult, financials: CanonicalFinancials) -> dict | None:
    if not result.can_score or result.quality_report.confidence not in PUBLIC_CONFIDENCE: return None
    company = financials.company
    return build_fundamental_screener_projection(market_code="FR", symbol=result.symbol, name=company.name, sector=None, currency=company.currency or "EUR", sec_facts=result.sec_facts, data_confidence=result.quality_report.confidence)


class _SingleIssuerFranceSource:
    def __init__(self, symbol, financials, shares): self.symbol, self.financials, self.shares = symbol, financials, shares
    def get_company_profile(self, symbol):
        item = self.financials.company
        return {"issuer_name": item.name, "exchange": item.exchange, "country": item.country, "currency": item.currency, "regulator_id": item.regulator_id, "security_type": item.security_type, "accounting_standard": item.accounting_standard}
    def get_financial_periods(self, symbol): return [{"fiscal_year": item.fiscal_year, "fiscal_period": item.fiscal_period, "period_end": item.period_end, "currency": item.currency} for item in self.financials.periods]
    def get_income_statements(self, symbol): return list(self.financials.income_statement)
    def get_balance_sheets(self, symbol): return list(self.financials.balance_sheet)
    def get_cash_flows(self, symbol): return list(self.financials.cash_flow)
    def get_filings(self, symbol): return self.get_source_documents(symbol)
    def get_shares_outstanding(self, symbol): return {"shares_outstanding": self.shares.shares_outstanding, "as_of": self.shares.as_of, "source": self.shares.source}
    def get_source_documents(self, symbol): return [_as_dict(item) for item in self.financials.source_documents]
    def get_statement_provenance(self, symbol): return [_as_dict(item) for item in self.financials.provenance]


def _as_dict(value) -> dict[str, Any]: return dict(value.__dict__)
