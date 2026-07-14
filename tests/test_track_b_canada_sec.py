from __future__ import annotations

from types import SimpleNamespace

import pytest

from codes.data.providers.canada_sec import (
    CanadaSecAcquisitionError,
    acquire_canada_sec_financials,
)
from codes.workers import canada_ingest_worker


class _Response:
    def __init__(self, *, payload=None, content=b""):
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self, ticker_map, submissions, companyfacts, filing_html=b""):
        self.ticker_map = ticker_map
        self.submissions = submissions
        self.companyfacts = companyfacts
        self.filing_html = filing_html
        self.urls = []

    def get(self, url, **_kwargs):
        self.urls.append(url)
        if url.endswith("company_tickers.json"):
            return _Response(payload=self.ticker_map)
        if "/submissions/" in url:
            return _Response(payload=self.submissions)
        if "/companyfacts/" in url:
            return _Response(payload=self.companyfacts)
        if "/Archives/" in url:
            return _Response(content=self.filing_html)
        raise AssertionError(f"unexpected URL: {url}")


def _entry(year, value, accession, *, duration=False):
    row = {
        "fy": year,
        "fp": "FY",
        "end": f"{year}-12-31",
        "val": value,
        "accn": accession,
        "filed": f"{year + 1}-02-15",
        "form": "40-F",
    }
    if duration:
        row["start"] = f"{year}-01-01"
    return row


def _concept(label, unit, values, *, duration=False):
    rows = [
        _entry(year, value, f"0001000000-{str(year + 1)[2:]}-000001", duration=duration)
        for year, value in values
    ]
    return {label: {"units": {unit: rows}}}


def _canadian_session(*, canadian=True):
    years = (2025, 2024, 2023)
    facts = {}
    facts.update(_concept("Revenue", "CAD", zip(years, (1300, 1200, 1100)), duration=True))
    facts.update(_concept("ProfitLoss", "CAD", zip(years, (130, 120, 110)), duration=True))
    facts.update(_concept("Assets", "CAD", zip(years, (1000, 900, 800))))
    facts.update(_concept("Liabilities", "CAD", zip(years, (400, 360, 320))))
    facts.update(_concept("Equity", "CAD", zip(years, (600, 540, 480))))
    facts.update(_concept(
        "CashFlowsFromUsedInOperatingActivities",
        "CAD",
        zip(years, (200, 180, 160)),
        duration=True,
    ))
    accession = "0001000000-26-000001"
    submissions = {
        "name": "CANADA FIXTURE INC.",
        "stateOfIncorporation": "A6" if canadian else "DE",
        "addresses": {
            "business": {
                "stateOrCountry": "A6" if canadian else "NY",
                "stateOrCountryDescription": "Ontario, Canada" if canadian else "New York",
            }
        },
        "filings": {"recent": {
            "form": ["40-F"],
            "filingDate": ["2026-02-15"],
            "reportDate": ["2025-12-31"],
            "accessionNumber": [accession],
            "primaryDocument": ["fixture-20251231.htm"],
        }},
    }
    filing_html = b"""
        <html><body>
          <xbrli:context id="class-a">
            <xbrli:entity><xbrli:segment>
              <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">ClassA</xbrldi:explicitMember>
            </xbrli:segment></xbrli:entity>
            <xbrli:period><xbrli:instant>2026-02-01</xbrli:instant></xbrli:period>
          </xbrli:context>
          <xbrli:context id="class-b">
            <xbrli:entity><xbrli:segment>
              <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">ClassB</xbrldi:explicitMember>
            </xbrli:segment></xbrli:entity>
            <xbrli:period><xbrli:instant>2026-02-01</xbrli:instant></xbrli:period>
          </xbrli:context>
          <ix:nonFraction name="dei:EntityCommonStockSharesOutstanding" contextRef="class-a" scale="0">900</ix:nonFraction>
          <ix:nonFraction name="dei:EntityCommonStockSharesOutstanding" contextRef="class-b" scale="0">100</ix:nonFraction>
        </body></html>
    """
    return _Session(
        {"0": {"ticker": "FIX", "cik_str": 1000000, "title": "CANADA FIXTURE INC."}},
        submissions,
        {"facts": {"ifrs-full": facts}},
        filing_html,
    )


def test_sec_acquisition_normalizes_ifrs_cad_and_class_shares():
    session = _canadian_session()

    financials, shares = acquire_canada_sec_financials(
        "FIX.TO",
        sec_ticker="FIX",
        session=session,
    )

    assert financials.company.exchange == "TSX"
    assert financials.company.currency == "CAD"
    assert [period.fiscal_year for period in financials.periods] == [2025, 2024, 2023]
    assert financials.income_statement[0]["revenue"] == 1300
    assert financials.balance_sheet[0]["total_assets"] == 1000
    assert financials.balance_sheet[0]["tot_lib"] == 400
    assert financials.cash_flow[0]["op_cf"] == 200
    assert shares.shares_outstanding == 1000
    assert shares.as_of == "2026-02-01"
    assert all(item.fiscal_year is not None for item in financials.provenance)
    assert all(item.confidence == "regulatory_verified" for item in financials.provenance)
    assert financials.source_documents[0].source == "SEC EDGAR"
    assert financials.source_documents[0].period_end == "2025-12-31"


def test_sec_acquisition_rejects_non_canadian_symbol_collision_before_facts_fetch():
    session = _canadian_session(canadian=False)

    with pytest.raises(CanadaSecAcquisitionError, match="does not identify that issuer as Canadian"):
        acquire_canada_sec_financials("FIX.TO", sec_ticker="FIX", session=session)

    assert not any("companyfacts" in url for url in session.urls)


def test_sec_acquisition_requires_three_aligned_fiscal_periods():
    session = _canadian_session()
    for concept in session.companyfacts["facts"]["ifrs-full"].values():
        concept["units"]["CAD"] = concept["units"]["CAD"][:2]

    with pytest.raises(CanadaSecAcquisitionError, match="at least 3 are required"):
        acquire_canada_sec_financials("FIX.TO", sec_ticker="FIX", session=session)


def test_worker_defaults_to_sec_without_csv_files(monkeypatch, capsys):
    result = SimpleNamespace(
        symbol="SHOP.TO",
        can_score=True,
        quality_report=SimpleNamespace(confidence="regulatory_verified", issues=()),
    )
    calls = []
    monkeypatch.setattr(
        canada_ingest_worker,
        "import_canada_sec_filings",
        lambda symbol, **kwargs: calls.append((symbol, kwargs)) or result,
    )

    exit_code = canada_ingest_worker.main(["--symbol", "SHOP.TO"])

    assert exit_code == 0
    assert calls == [("SHOP.TO", {"sec_ticker": None, "years": 11})]
    assert "SHOP.TO public_score_ready target=market_db source=sec_edgar" in capsys.readouterr().out


def test_worker_reports_unsupported_sec_issuer_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(
        canada_ingest_worker,
        "import_canada_sec_filings",
        lambda *args, **kwargs: (_ for _ in ()).throw(CanadaSecAcquisitionError("no annual XBRL")),
    )

    exit_code = canada_ingest_worker.main(["--symbol", "PRIVATE.V"])

    error = capsys.readouterr().err
    assert exit_code == 2
    assert "no annual XBRL" in error
    assert "No data was written" in error
    assert "Traceback" not in error
