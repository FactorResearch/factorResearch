import csv

import pytest

from codes.data.providers import CanonicalSharesOutstanding
from codes.data.providers.canada_ingestion import (
    CanadaVerifiedCsvBundle,
    import_canada_verified_csv_bundle,
    load_canada_verified_csv_bundle,
)
from codes.workers import canada_ingest_worker


def _write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _bundle(tmp_path, *, bad_document_ref=False, confidence="regulatory_verified"):
    company_csv = tmp_path / "company.csv"
    periods_csv = tmp_path / "periods.csv"
    documents_csv = tmp_path / "documents.csv"
    facts_csv = tmp_path / "facts.csv"
    shares_csv = tmp_path / "shares.csv"

    _write_csv(company_csv, ["symbol", "name", "exchange", "country", "currency"], [{
        "symbol": "SHOP.TO",
        "name": "Shopify Inc.",
        "exchange": "TSX",
        "country": "Canada",
        "currency": "CAD",
    }])
    _write_csv(periods_csv, ["symbol", "fiscal_year", "fiscal_period", "period_end", "currency"], [{
        "symbol": "SHOP.TO",
        "fiscal_year": "2025",
        "fiscal_period": "FY",
        "period_end": "2025-12-31",
        "currency": "CAD",
    }])
    _write_csv(
        documents_csv,
        ["document_id", "source", "url", "filing_date", "period_end", "form", "confidence"],
        [{
            "document_id": "sedar-shop-2025",
            "source": "SEDAR+",
            "url": "https://example.test/sedar/shop-2025",
            "filing_date": "2026-02-15",
            "period_end": "2025-12-31",
            "form": "Annual financial statements",
            "confidence": confidence,
        }],
    )
    facts = [
        ("income", "revenue", "1000000"),
        ("income", "net_inc", "120000"),
        ("balance", "total_assets", "800000"),
        ("balance", "tot_lib", "300000"),
        ("balance", "equity", "500000"),
        ("cash_flow", "operating_cash_flow", "150000"),
    ]
    _write_csv(
        facts_csv,
        [
            "symbol", "statement_type", "fact_name", "fiscal_year", "fiscal_period",
            "period_end", "currency", "value", "source_document_id", "source_url",
            "confidence", "accounting_standard", "extraction_method", "normalization_method",
        ],
        [{
            "symbol": "SHOP.TO",
            "statement_type": statement,
            "fact_name": fact,
            "fiscal_year": "2025",
            "fiscal_period": "FY",
            "period_end": "2025-12-31",
            "currency": "CAD",
            "value": value,
            "source_document_id": "missing-doc" if bad_document_ref else "sedar-shop-2025",
            "source_url": "https://example.test/sedar/shop-2025",
            "confidence": confidence,
            "accounting_standard": "IFRS",
            "extraction_method": "fixture",
            "normalization_method": "canada_verified_csv",
        } for statement, fact, value in facts],
    )
    _write_csv(shares_csv, ["symbol", "shares_outstanding", "as_of", "source"], [{
        "symbol": "SHOP.TO",
        "shares_outstanding": "1234000",
        "as_of": "2026-01-31",
        "source": "SEDAR+",
    }])
    return CanadaVerifiedCsvBundle(company_csv, periods_csv, documents_csv, facts_csv, shares_csv)


def test_canada_verified_csv_bundle_loads_canonical_payload(tmp_path):
    financials, shares = load_canada_verified_csv_bundle("shop:tsx", _bundle(tmp_path))

    assert financials.company.symbol == "SHOP.TO"
    assert financials.company.currency == "CAD"
    assert financials.periods[0].fiscal_year == 2025
    assert financials.income_statement[0]["revenue"] == 1_000_000
    assert financials.balance_sheet[0]["total_assets"] == 800_000
    assert financials.source_documents[0].document_id == "sedar-shop-2025"
    assert financials.provenance[0].accounting_standard == "IFRS"
    assert isinstance(shares, CanonicalSharesOutstanding)
    assert shares.shares_outstanding == 1_234_000


def test_canada_verified_csv_bundle_rejects_unknown_document(tmp_path):
    with pytest.raises(ValueError, match="unknown source document"):
        load_canada_verified_csv_bundle("SHOP.TO", _bundle(tmp_path, bad_document_ref=True))


def test_canada_verified_csv_import_persists_without_json_files(tmp_path, monkeypatch):
    saved = {}

    def _save(symbol, financials, shares, allow_internal=False):
        saved["symbol"] = symbol
        saved["financials"] = financials
        saved["shares"] = shares
        saved["allow_internal"] = allow_internal
        from codes.data.providers.canada_db import ingest_verified_canada_financials

        return ingest_verified_canada_financials(symbol, financials, shares, allow_internal=allow_internal)

    monkeypatch.setattr("codes.data.providers.canada_ingestion.ingest_verified_canada_financials", _save)
    monkeypatch.setattr("codes.data.providers.canada_db.db.upsert_canada_canonical_facts", lambda *args: None)

    result = import_canada_verified_csv_bundle("shop:tsx", _bundle(tmp_path))

    assert result.can_score is True
    assert saved["symbol"] == "SHOP.TO"
    assert saved["allow_internal"] is False
    assert list(tmp_path.glob("*.json")) == []


def test_canada_ingest_worker_reports_status(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("codes.data.providers.canada_db.db.upsert_canada_canonical_facts", lambda *args: None)
    bundle = _bundle(tmp_path)

    exit_code = canada_ingest_worker.main([
        "--symbol", "SHOP.TO",
        "--company-csv", str(bundle.company_csv),
        "--periods-csv", str(bundle.periods_csv),
        "--documents-csv", str(bundle.documents_csv),
        "--facts-csv", str(bundle.facts_csv),
        "--shares-csv", str(bundle.shares_csv),
    ])

    assert exit_code == 0
    assert "SHOP.TO score_ready confidence=regulatory_verified" in capsys.readouterr().out
