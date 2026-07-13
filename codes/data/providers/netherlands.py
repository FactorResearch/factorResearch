"""Netherlands market adapter for source-verified canonical facts."""
from __future__ import annotations
from typing import Any, Protocol
from . import CanonicalCompany, CanonicalCurrency, CanonicalFinancials, CanonicalFiscalPeriod, CanonicalSharesOutstanding, FilingDocument, StatementProvenance

class NetherlandsDataSource(Protocol):
    def get_company_profile(self, symbol: str) -> dict[str, Any] | None: ...
    def get_financial_periods(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_income_statements(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_balance_sheets(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_cash_flows(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_filings(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_shares_outstanding(self, symbol: str) -> dict[str, Any] | None: ...
    def get_source_documents(self, symbol: str) -> list[dict[str, Any]]: ...
    def get_statement_provenance(self, symbol: str) -> list[dict[str, Any]]: ...

class EmptyNetherlandsDataSource:
    def get_company_profile(self, symbol): return None
    def get_financial_periods(self, symbol): return []
    def get_income_statements(self, symbol): return []
    def get_balance_sheets(self, symbol): return []
    def get_cash_flows(self, symbol): return []
    def get_filings(self, symbol): return []
    def get_shares_outstanding(self, symbol): return None
    def get_source_documents(self, symbol): return []
    def get_statement_provenance(self, symbol): return []

class NetherlandsProviderAdapter:
    provider_name, country, default_currency = "netherlands", "Netherlands", "EUR"
    supported_exchanges = ("EURONEXT AMSTERDAM", "XAMS")
    def __init__(self, source: NetherlandsDataSource | None = None): self.source = source or EmptyNetherlandsDataSource()
    def get_company(self, symbol):
        symbol = normalize_netherlands_symbol(symbol); row = self.source.get_company_profile(symbol) or {}
        return CanonicalCompany(symbol, row.get("name") or row.get("issuer_name"), row.get("exchange"), self.country, row.get("currency") or self.default_currency, row.get("regulator_id") or row.get("lei") or row.get("afm_id"), row.get("security_type"), row.get("accounting_standard"))
    def get_financials(self, symbol):
        symbol, company = normalize_netherlands_symbol(symbol), self.get_company(symbol)
        return CanonicalFinancials(company, tuple(item for row in self.source.get_financial_periods(symbol) if (item := _period(row, company.currency))), tuple(self.source.get_income_statements(symbol)), tuple(self.source.get_balance_sheets(symbol)), tuple(self.source.get_cash_flows(symbol)), tuple(self.get_source_documents(symbol)), tuple(self.get_statement_provenance(symbol)))
    def get_filings(self, symbol): return list(self.source.get_filings(normalize_netherlands_symbol(symbol)))
    def get_shares_outstanding(self, symbol):
        symbol = normalize_netherlands_symbol(symbol); row = self.source.get_shares_outstanding(symbol) or {}
        return CanonicalSharesOutstanding(symbol, _float(row.get("shares_outstanding") or row.get("shares")), row.get("as_of") or row.get("date"), row.get("source"))
    def get_shares(self, symbol):
        item = self.get_shares_outstanding(symbol); return {"symbol": item.symbol, "shares_outstanding": item.shares_outstanding, "as_of": item.as_of, "source": item.source}
    def get_source_documents(self, symbol): return [_document(row) for row in self.source.get_source_documents(normalize_netherlands_symbol(symbol))]
    def get_statement_provenance(self, symbol): return [_provenance(row) for row in self.source.get_statement_provenance(normalize_netherlands_symbol(symbol))]
    def get_currency(self, symbol): return self.get_company(symbol).currency
    def get_currency_info(self, symbol): return CanonicalCurrency(self.get_currency(symbol) or self.default_currency, "Euro")
    def get_listing_information(self, symbol):
        item = self.get_company(symbol); return {"symbol": item.symbol, "exchange": item.exchange, "country": item.country, "currency": item.currency, "regulator_id": item.regulator_id, "security_type": item.security_type, "accounting_standard": item.accounting_standard, "supported_exchanges": list(self.supported_exchanges)}

def normalize_netherlands_symbol(symbol):
    value = str(symbol or "").upper().strip().replace(":", ".")
    return value[:-9] + ".AS" if value.endswith(".EURONEXT") else value
def is_netherlands_symbol(symbol): return normalize_netherlands_symbol(symbol).endswith(".AS")
def _period(row, fallback):
    try: year = int(row.get("fiscal_year") or row.get("year"))
    except (TypeError, ValueError): return None
    end = row.get("period_end") or row.get("end_date")
    return CanonicalFiscalPeriod(year, str(row.get("fiscal_period") or row.get("period") or "FY"), str(end), row.get("currency") or fallback) if end else None
def _document(row): return FilingDocument(str(row.get("document_id") or row.get("id") or ""), str(row.get("source") or "unknown"), row.get("url"), row.get("filing_date") or row.get("date"), row.get("period_end"), row.get("form") or row.get("document_type"), row.get("confidence") or "insufficient_source_evidence")
def _provenance(row):
    try: year = int(row.get("fiscal_year") or row.get("year"))
    except (TypeError, ValueError): year = None
    return StatementProvenance(str(row.get("fact_name") or row.get("field") or ""), str(row.get("source_document_id") or row.get("document_id") or ""), row.get("source_url") or row.get("url"), row.get("confidence") or "insufficient_source_evidence", row.get("accounting_standard"), row.get("extraction_method"), row.get("normalization_method"), year, row.get("fiscal_period") or row.get("period"))
def _float(value):
    try: return float(value)
    except (TypeError, ValueError): return None
