from dataclasses import replace
from unittest.mock import patch

from codes.data.providers import (
    CanonicalCompany,
    CanonicalFinancials,
    CanonicalFiscalPeriod,
    CanonicalSharesOutstanding,
    FilingDocument,
    StatementProvenance,
)
from codes.data.providers import registry
from codes.data.providers.uk import UKProviderAdapter, is_uk_symbol, normalize_uk_symbol
from codes.data.providers.uk_db import UKDatabaseDataSource, ingest_verified_uk_financials
from codes.data.providers.uk_ingestion import UKVerifiedCsvBundle, load_uk_verified_csv_bundle
from codes.data.providers.uk_normalization import build_uk_scoring_facts


REQUIRED_FACTS = ("revenue", "net_inc", "total_assets", "tot_lib", "equity")


class _Source:
    def __init__(self, financials, shares):
        self.financials = financials
        self.shares = shares

    def get_company_profile(self, _symbol):
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

    def get_financial_periods(self, _symbol):
        return [period.__dict__ for period in self.financials.periods]

    def get_income_statements(self, _symbol):
        return list(self.financials.income_statement)

    def get_balance_sheets(self, _symbol):
        return list(self.financials.balance_sheet)

    def get_cash_flows(self, _symbol):
        return list(self.financials.cash_flow)

    def get_filings(self, _symbol):
        return [document.__dict__ for document in self.financials.source_documents]

    def get_shares_outstanding(self, _symbol):
        return self.shares.__dict__

    def get_source_documents(self, _symbol):
        return [document.__dict__ for document in self.financials.source_documents]

    def get_statement_provenance(self, _symbol):
        return [item.__dict__ for item in self.financials.provenance]


def _financials(*, security_type="ordinary_share", accounting_standard="UK-adopted IFRS"):
    years = (2025, 2024, 2023)
    documents = tuple(
        FilingDocument(
            document_id=f"fca-vod-{year}",
            source="FCA NSM",
            url=f"https://data.fca.org.uk/example/{year}",
            filing_date=f"{year + 1}-03-01",
            period_end=f"{year}-12-31",
            form="Annual Financial Report",
            confidence="regulatory_verified",
        )
        for year in years
    )
    provenance = tuple(
        StatementProvenance(
            fact_name=fact,
            source_document_id=f"fca-vod-{year}",
            source_url=f"https://data.fca.org.uk/example/{year}",
            confidence="regulatory_verified",
            accounting_standard=accounting_standard,
            extraction_method="ixbrl",
            normalization_method="uk_v1",
            fiscal_year=year,
            fiscal_period="FY",
        )
        for year in years
        for fact in REQUIRED_FACTS
    )
    return CanonicalFinancials(
        company=CanonicalCompany(
            symbol="VOD.L",
            name="Vodafone Group Plc",
            exchange="LSE",
            country="United Kingdom",
            currency="GBP",
            regulator_id="01833679",
            security_type=security_type,
            accounting_standard=accounting_standard,
        ),
        periods=tuple(
            CanonicalFiscalPeriod(year, "FY", f"{year}-12-31", "GBP")
            for year in years
        ),
        income_statement=tuple({
            "fiscal_year": year,
            "fiscal_period": "FY",
            "period_end": f"{year}-12-31",
            "currency": "GBP",
            "revenue": 1_000 - (2025 - year) * 50,
            "net_inc": 100 - (2025 - year) * 5,
        } for year in years),
        balance_sheet=tuple({
            "fiscal_year": year,
            "fiscal_period": "FY",
            "period_end": f"{year}-12-31",
            "currency": "GBP",
            "total_assets": 800 - (2025 - year) * 20,
            "tot_lib": 300 - (2025 - year) * 10,
            "equity": 500 - (2025 - year) * 10,
        } for year in years),
        source_documents=documents,
        provenance=provenance,
    )


def _shares():
    return CanonicalSharesOutstanding(
        symbol="VOD.L",
        shares_outstanding=2_500,
        as_of="2026-02-28",
        source="FCA NSM annual report",
    )


def test_uk_symbol_and_provider_metadata():
    financials = _financials()
    provider = UKProviderAdapter(_Source(financials, _shares()))

    assert normalize_uk_symbol("vod:lse") == "VOD.L"
    assert is_uk_symbol("VOD.L") is True
    assert is_uk_symbol("VOD") is False
    assert provider.get_currency("VOD.L") == "GBP"
    assert provider.get_listing_information("VOD.L")["security_type"] == "ordinary_share"


def test_uk_verified_ordinary_share_builds_scoring_facts():
    financials = _financials()
    result = build_uk_scoring_facts(UKProviderAdapter(_Source(financials, _shares())), "vod:lse")

    assert result.can_score is True
    assert result.quality_report.market == "GB"
    assert result.sec_facts["source_regulator"] == "FCA NSM"
    assert result.sec_facts["source_country"] == "United Kingdom"
    assert result.sec_facts["security_type"] == "ordinary_share"
    assert result.sec_facts["revenue"][0]["currency"] == "GBP"


def test_uk_adr_and_investment_trust_do_not_use_operating_company_score():
    for security_type in ("adr", "investment_trust"):
        financials = _financials(security_type=security_type)
        result = build_uk_scoring_facts(
            UKProviderAdapter(_Source(financials, _shares())),
            "VOD.L",
        )
        assert result.can_score is False
        assert "unsupported_scoring_security_type" in {
            issue.code for issue in result.quality_report.issues
        }


def test_uk_requires_explicit_supported_accounting_standard():
    financials = _financials(accounting_standard="unknown")
    result = build_uk_scoring_facts(UKProviderAdapter(_Source(financials, _shares())), "VOD.L")

    assert result.can_score is False
    assert "unsupported_accounting_standard" in {
        issue.code for issue in result.quality_report.issues
    }


def test_uk_requires_three_aligned_annual_periods():
    financials = _financials()
    one_year = replace(
        financials,
        periods=financials.periods[:1],
        income_statement=financials.income_statement[:1],
        balance_sheet=financials.balance_sheet[:1],
        source_documents=financials.source_documents[:1],
        provenance=tuple(item for item in financials.provenance if item.fiscal_year == 2025),
    )
    result = build_uk_scoring_facts(UKProviderAdapter(_Source(one_year, _shares())), "VOD.L")

    assert result.can_score is False
    assert "insufficient_annual_history" in {
        issue.code for issue in result.quality_report.issues
    }


def test_uk_database_source_uses_generic_market_tables():
    source = UKDatabaseDataSource()
    with patch.object(registry.app_flags, "is_market_enabled", return_value=True), \
         patch("codes.data.providers.uk_db.db.get_market_company_profile", return_value={"issuer_name": "Vodafone"}) as company, \
         patch("codes.data.providers.uk_db.db.get_market_financial_periods", return_value=[]) as periods:
        assert source.get_company_profile("vod:lse")["issuer_name"] == "Vodafone"
        assert source.get_financial_periods("vod:lse") == []

    company.assert_called_once_with("GB", "VOD.L")
    periods.assert_called_once_with("GB", "VOD.L")


def test_uk_ingest_writes_market_code_and_public_projection():
    financials = _financials()
    with patch("codes.data.providers.uk_db.db.upsert_market_canonical_facts") as save:
        result = ingest_verified_uk_financials("vod:lse", financials, _shares())

    assert result.can_score is True
    assert save.call_args.args[0:2] == ("GB", "VOD.L")
    assert save.call_args.kwargs["screener_row"]["market_code"] == "GB"


def test_uk_provider_only_data_requires_explicit_internal_mode():
    financials = _financials()
    internal = replace(
        financials,
        source_documents=tuple(
            replace(document, source="FMP", confidence="provider_normalized_internal_only")
            for document in financials.source_documents
        ),
        provenance=tuple(
            replace(item, confidence="provider_normalized_internal_only")
            for item in financials.provenance
        ),
    )
    with patch("codes.data.providers.uk_db.db.upsert_market_canonical_facts") as save:
        try:
            ingest_verified_uk_financials("VOD.L", internal, _shares())
        except ValueError as exc:
            assert "allow_internal=True" in str(exc)
        else:
            raise AssertionError("provider-only data must require explicit internal mode")
    save.assert_not_called()


def test_registry_routes_enabled_uk_and_fails_closed_when_disabled():
    with patch.object(registry, "is_market_enabled", return_value=True):
        assert registry.provider_for_symbol("VOD.L").provider_name == "uk"
    with patch.object(registry, "is_market_enabled", return_value=False):
        assert registry.provider_for_symbol("VOD.L") is None
        try:
            registry.require_symbol_market_enabled("VOD.L")
        except ValueError as exc:
            assert "disabled" in str(exc)
        else:
            raise AssertionError("disabled UK market must fail closed")


def test_disabled_uk_market_blocks_cached_analysis(monkeypatch):
    from codes.app_modules import analysis

    monkeypatch.setattr(analysis, "require_symbol_market_enabled", registry.require_symbol_market_enabled)
    monkeypatch.setattr(registry, "is_market_enabled", lambda _code: False)
    analysis._analysis_cache["VOD.L"] = {"symbol": "VOD.L", "name": "stale"}
    try:
        result = analysis.analyze_stock("VOD.L")
    finally:
        analysis._analysis_cache.pop("VOD.L", None)

    assert result == {"error": "United Kingdom market support is disabled."}


def test_uk_verified_bundle_loads_from_directory_files(tmp_path):
    (tmp_path / "company.csv").write_text(
        "symbol,name,exchange,country,currency,company_number,security_type,accounting_standard\n"
        "VOD.L,Vodafone Group Plc,LSE,United Kingdom,GBP,01833679,ordinary_share,UK-adopted IFRS\n"
    )
    (tmp_path / "periods.csv").write_text(
        "symbol,fiscal_year,fiscal_period,period_end,currency\n"
        "VOD.L,2025,FY,2025-12-31,GBP\n"
    )
    (tmp_path / "documents.csv").write_text(
        "document_id,source,url,filing_date,period_end,form,confidence\n"
        "fca-vod-2025,FCA NSM,https://data.fca.org.uk/example,2026-03-01,2025-12-31,Annual Financial Report,regulatory_verified\n"
    )
    fact_rows = [
        "statement_type,fact_name,value,symbol,fiscal_year,fiscal_period,period_end,currency,source_document_id,confidence,accounting_standard\n",
        "income,revenue,1000,VOD.L,2025,FY,2025-12-31,GBP,fca-vod-2025,regulatory_verified,UK-adopted IFRS\n",
        "income,net_inc,100,VOD.L,2025,FY,2025-12-31,GBP,fca-vod-2025,regulatory_verified,UK-adopted IFRS\n",
        "balance,total_assets,800,VOD.L,2025,FY,2025-12-31,GBP,fca-vod-2025,regulatory_verified,UK-adopted IFRS\n",
        "balance,tot_lib,300,VOD.L,2025,FY,2025-12-31,GBP,fca-vod-2025,regulatory_verified,UK-adopted IFRS\n",
        "balance,equity,500,VOD.L,2025,FY,2025-12-31,GBP,fca-vod-2025,regulatory_verified,UK-adopted IFRS\n",
    ]
    (tmp_path / "facts.csv").write_text("".join(fact_rows))
    (tmp_path / "shares.csv").write_text(
        "symbol,shares_outstanding,as_of,source\n"
        "VOD.L,2500,2026-02-28,FCA NSM annual report\n"
    )
    bundle = UKVerifiedCsvBundle(*(
        tmp_path / name
        for name in ("company.csv", "periods.csv", "documents.csv", "facts.csv", "shares.csv")
    ))

    financials, shares = load_uk_verified_csv_bundle("VOD.L", bundle)

    assert financials.company.regulator_id == "01833679"
    assert financials.company.security_type == "ordinary_share"
    assert financials.income_statement[0]["revenue"] == 1000
    assert shares.shares_outstanding == 2500
