import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.data import api_fetcher


def test_institutional_ownership_trends_aggregate_by_quarter():
    fake_client = Mock()
    fake_client.institutional_ownership.return_value = {
        "data": [
            {"reportDate": "2026-03-31", "share": 100},
            {"reportDate": "2026-03-15", "share": 50},
            {"reportDate": "2026-06-30", "share": 180},
        ]
    }

    with patch.object(api_fetcher, "_fh_client", fake_client), \
         patch.object(api_fetcher._fh_limiter, "check"), \
         patch.object(api_fetcher._fh_limiter, "record"):
        trends = api_fetcher._fh_get_institutional_ownership_trends("MSFT")

    assert trends == [
        {"period": "2026-Q1", "value": 150.0},
        {"period": "2026-Q2", "value": 180.0},
    ]
    fake_client.institutional_ownership.assert_called_once()


def test_patent_trends_aggregate_by_year_count():
    fake_client = Mock()
    fake_client.stock_uspto_patent.return_value = {
        "data": [
            {"filingDate": "2025-01-10", "patentNumber": "A"},
            {"filingDate": "2025-08-20", "patentNumber": "B"},
            {"filingDate": "2026-02-01", "patentNumber": "C"},
        ]
    }

    with patch.object(api_fetcher, "_fh_client", fake_client), \
         patch.object(api_fetcher._fh_limiter, "check"), \
         patch.object(api_fetcher._fh_limiter, "record"):
        trends = api_fetcher._fh_get_patent_trends("AAPL")

    assert trends == [
        {"period": "2025", "value": 2.0},
        {"period": "2026", "value": 1.0},
    ]
    fake_client.stock_uspto_patent.assert_called_once()


def test_phase_e_provider_fetchers_use_cache():
    with patch("codes.data.api_fetcher.read", return_value=[{"period": "2026-Q1", "value": 1}]), \
         patch("codes.data.api_fetcher._fh_get_institutional_ownership_trends") as ownership_fetch, \
         patch("codes.data.api_fetcher._fh_get_patent_trends") as patent_fetch:
        assert api_fetcher.get_institutional_ownership_trends("MSFT") == [
            {"period": "2026-Q1", "value": 1}
        ]
        assert api_fetcher.get_patent_trends("MSFT") == [
            {"period": "2026-Q1", "value": 1}
        ]

    ownership_fetch.assert_not_called()
    patent_fetch.assert_not_called()
