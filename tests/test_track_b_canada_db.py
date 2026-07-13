from contextlib import contextmanager

from codes.data import db
from codes.data.providers import (
    CanonicalCompany,
    CanonicalFinancials,
    CanonicalFiscalPeriod,
    CanonicalSharesOutstanding,
    DataQualityReport,
    FilingDocument,
    StatementProvenance,
)
from codes.data.providers.canada_db import (
    CanadaDatabaseDataSource,
    ingest_verified_canada_financials,
)


class _FakeResult:
    def __init__(self, rows=None, row=None):
        self._rows = rows or []
        self._row = row

    def fetchall(self):
        return self._rows

    def fetchone(self):
        if self._row is not None:
            return self._row
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, rows=None, row=None):
        self.calls = []
        self.row_factory = None
        self._rows = rows or []
        self._row = row

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return _FakeResult(rows=self._rows, row=self._row)


@contextmanager
def _ctx(conn):
    yield conn


def _financials(confidence="regulatory_verified"):
    company = CanonicalCompany(
        symbol="SHOP.TO",
        name="Shopify Inc.",
        exchange="TSX",
        country="Canada",
        currency="CAD",
    )
    period = CanonicalFiscalPeriod(2025, "FY", "2025-12-31", "CAD")
    document = FilingDocument(
        document_id="sedar-shop-2025",
        source="SEDAR+",
        url="https://example.test/sedar/shop-2025",
        filing_date="2026-02-15",
        period_end="2025-12-31",
        form="Annual financial statements",
        confidence=confidence,
    )
    fields = (
        "revenue", "net_inc", "op_income", "total_assets", "tot_lib", "equity",
        "operating_cash_flow", "capex",
    )
    provenance = tuple(
        StatementProvenance(
            fact_name=field,
            source_document_id=document.document_id,
            source_url=document.url,
            confidence=confidence,
            accounting_standard="IFRS",
            extraction_method="fixture",
            normalization_method="canada_v1",
        )
        for field in fields
    )
    return CanonicalFinancials(
        company=company,
        periods=(period,),
        income_statement=({
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "currency": "CAD",
            "revenue": 1_000_000,
            "net_inc": 120_000,
            "op_income": 160_000,
        },),
        balance_sheet=({
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "currency": "CAD",
            "total_assets": 800_000,
            "tot_lib": 300_000,
            "equity": 500_000,
        },),
        cash_flow=({
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "currency": "CAD",
            "operating_cash_flow": 150_000,
            "capex": 40_000,
        },),
        source_documents=(document,),
        provenance=provenance,
    )


def _shares():
    return CanonicalSharesOutstanding(
        symbol="SHOP.TO",
        shares_outstanding=1_234_000,
        as_of="2026-01-31",
        source="SEDAR+",
    )


def test_canada_canonical_facts_are_persisted_relationally(monkeypatch):
    conn = _FakeConn()
    monkeypatch.setattr(db, "_market_initialized", True)
    monkeypatch.setattr(db, "_conn", lambda: _ctx(conn))

    db.upsert_canada_canonical_facts(
        "shop.to",
        _financials(),
        _shares(),
        DataQualityReport("CA", True, "regulatory_verified"),
    )

    sql_text = "\n".join(sql for sql, _params in conn.calls)
    assert "canada_issuers" in sql_text
    assert "canada_statement_facts" in sql_text
    assert "canada_shares_outstanding" in sql_text
    assert "data_json" not in sql_text
    fact_params = [
        params
        for sql, params in conn.calls
        if "canada_statement_facts" in sql and params and "fact_name" in params
    ]
    assert {params["fact_name"] for params in fact_params} >= {"revenue", "net_inc", "total_assets"}
    assert all(params["currency"] == "CAD" for params in fact_params)
    assert all(params["source_document_id"] == "sedar-shop-2025" for params in fact_params)


def test_canada_database_source_reads_normalized_rows(monkeypatch):
    monkeypatch.setattr(db, "get_canada_company_profile", lambda symbol: {"issuer_name": "Shopify Inc."})
    monkeypatch.setattr(db, "get_canada_financial_periods", lambda symbol: [{"fiscal_year": 2025}])
    monkeypatch.setattr(db, "get_canada_statement_facts", lambda symbol, statement: [{"statement": statement}])
    monkeypatch.setattr(db, "get_canada_filings", lambda symbol: [{"document_id": "sedar-shop-2025"}])
    monkeypatch.setattr(db, "get_canada_shares_outstanding", lambda symbol: {"shares_outstanding": 1234})
    monkeypatch.setattr(db, "get_canada_source_documents", lambda symbol: [{"document_id": "sedar-shop-2025"}])
    monkeypatch.setattr(db, "get_canada_statement_provenance", lambda symbol: [{"fact_name": "revenue"}])

    source = CanadaDatabaseDataSource()

    assert source.get_company_profile("shop:tsx")["issuer_name"] == "Shopify Inc."
    assert source.get_financial_periods("shop:tsx")[0]["fiscal_year"] == 2025
    assert source.get_income_statements("shop:tsx")[0]["statement"] == "income"
    assert source.get_balance_sheets("shop:tsx")[0]["statement"] == "balance"
    assert source.get_cash_flows("shop:tsx")[0]["statement"] == "cash_flow"
    assert source.get_filings("shop:tsx")[0]["document_id"] == "sedar-shop-2025"
    assert source.get_shares_outstanding("shop:tsx")["shares_outstanding"] == 1234
    assert source.get_source_documents("shop:tsx")[0]["document_id"] == "sedar-shop-2025"
    assert source.get_statement_provenance("shop:tsx")[0]["fact_name"] == "revenue"


def test_ingest_verified_canada_financials_stores_quality_report(monkeypatch):
    saved = {}

    def _save(symbol, financials, shares, quality_report):
        saved["symbol"] = symbol
        saved["financials"] = financials
        saved["shares"] = shares
        saved["quality_report"] = quality_report

    monkeypatch.setattr(db, "upsert_canada_canonical_facts", _save)

    result = ingest_verified_canada_financials("shop:tsx", _financials(), _shares())

    assert result.can_score is True
    assert saved["symbol"] == "SHOP.TO"
    assert saved["quality_report"].can_score is True
    assert saved["quality_report"].confidence == "regulatory_verified"
