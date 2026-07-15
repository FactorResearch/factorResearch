from unittest.mock import patch
from datetime import datetime

import pytest

from codes.data import sec_data


def test_missing_sec_metadata_is_stale():
    with patch.object(sec_data.db, "get_sec_facts_meta", return_value=None):
        assert sec_data.is_cache_stale("aapl") is True


def test_recent_filing_metadata_is_fresh():
    meta = {
        "updated_at": datetime.now().isoformat(),
        "latest_filing": "2026-06-30",
    }
    with patch.object(sec_data.db, "get_sec_facts_meta", return_value=meta):
        assert sec_data.is_cache_stale("AAPL") is False


def test_refresh_returns_fresh_database_facts_without_network():
    facts = {"name": "Apple Inc."}
    with patch.object(sec_data, "is_cache_stale", return_value=False), \
         patch.object(sec_data.db, "get_sec_facts", return_value=facts), \
         patch.object(sec_data, "fetch_company_facts") as fetch:
        assert sec_data.refresh_if_needed("AAPL") == facts
    fetch.assert_not_called()


def test_app_financials_are_database_only_and_normalize_symbol():
    facts = {"name": "Apple Inc."}
    with patch.object(sec_data.db, "get_sec_facts", return_value=facts) as read, \
         patch.object(sec_data, "fetch_company_facts") as fetch:
        assert sec_data.get_financials(" aapl ", force_refresh=True) == facts
    read.assert_called_once_with("AAPL")
    fetch.assert_not_called()


def test_missing_database_facts_queue_user_facing_retry():
    with patch.object(sec_data.db, "get_sec_facts", return_value=None):
        with pytest.raises(ValueError, match="next background refresh"):
            sec_data.get_financials("AAPL")
