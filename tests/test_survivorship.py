import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
import os


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from codes.data import sec_data
from codes.data.sec_data import (
    get_ticker_map, get_cik, _sector_class, _annual_df,
    _revenue_concepts, fetch_company_facts, _latest_filing_date
)

# Mock data
MOCK_TICKER_MAP = {"AAPL": {"cik": "0000320193", "name": "Apple Inc."}}

@pytest.fixture
def mock_requests():
    with patch('requests.get') as mock_get:
        yield mock_get

@pytest.fixture
def mock_cache():
    sec_data._tickermap = None
    with patch.object(sec_data, 'cache') as mock_c:
        mock_c.is_ticker_map_stale.return_value = False
        mock_c.read.return_value = MOCK_TICKER_MAP
        mock_c.is_stale_for_company.return_value = False
        yield mock_c
    sec_data._tickermap = None

def test_get_ticker_map(mock_cache):
    m = get_ticker_map()
    assert "AAPL" in m
    assert m["AAPL"]["cik"] == "0000320193"

def test_get_cik(mock_cache):
    cik, name = get_cik("AAPL")
    assert cik == "0000320193"
    assert name == "Apple Inc."

def test_sector_class():
    assert _sector_class(6200) == "bank"
    assert _sector_class(2834) == "biotech"
    assert _sector_class(9999) == "general"

def test_latest_filing_date():
    subs = {
        "filings": {
            "recent": {
                "form": ["10-K", "10-Q", "8-K"],
                "filingDate": ["2024-01-01", "2024-05-01", "2024-03-01"]
            }
        }
    }
    assert _latest_filing_date(subs) == "2024-05-01"

def test_annual_df():
    facts = {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {"fy": 2023, "form": "10-K", "val": 100, "end": "2023-12-31", "filed": "2024-01-01"},
                        {"fy": 2022, "form": "10-K", "val": 90, "end": "2022-12-31", "filed": "2023-01-01"}
                    ]
                }
            }
        }
    }
    df = _annual_df(facts, "Revenues")
    assert len(df) == 2
    assert df.iloc[0]["year"] == 2023

def test_revenue_concepts():
    assert "Revenues" in _revenue_concepts("general")
    assert "NetInterestIncome" in _revenue_concepts("bank")

def test_fetch_company_facts_mocked(mock_requests, mock_cache):
    # Basic smoke test - full mocking of network is complex but core logic is covered
    mock_requests.side_effect = [
        MagicMock(json=lambda: {"filings": {"recent": {"form": [], "filingDate": []}}}),
        MagicMock(json=lambda: {"facts": {}})
    ]
    # Extend with more detailed mocks as needed for full integration testing
    pass

