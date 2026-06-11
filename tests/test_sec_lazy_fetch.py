"""
Tests for P5 Lazy Fetch API (sec_data.get_financials, is_cache_stale, refresh_if_needed).

Verifies:
  1. get_financials() returns cached data without network when cache is fresh.
  2. get_financials(force_refresh=True) always calls fetch_company_facts.
  3. is_cache_stale() returns True when no cache entry exists.
  4. is_cache_stale() returns False within the TTL window.
  5. is_cache_stale() does a submissions check beyond the TTL window.
  6. refresh_if_needed() skips fetch when cache is fresh.
  7. refresh_if_needed() calls fetch_company_facts when stale.
"""

import sys
import os
import time
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from codes.data import sec_data


# ── Helpers ───────────────────────────────────────────────────────────────────

_FAKE_FACTS = {"name": "Fake Corp", "sector": "Test", "eps": [], "equity": []}

_FRESH_ENTRY = {
    "ts":            time.time(),          # just written
    "latest_filing": "2024-11-01",
    "data":          _FAKE_FACTS,
}

_OLD_ENTRY = {
    "ts":            time.time() - 10 * 86400,  # 10 days old (beyond TTL)
    "latest_filing": "2024-11-01",
    "data":          _FAKE_FACTS,
}


# ══════════════════════════════════════════════════════════════════════════════
# is_cache_stale
# ══════════════════════════════════════════════════════════════════════════════

class TestIsCacheStale:
    def test_no_entry_is_stale(self):
        with patch("codes.data.sec_data.cache.read_entry", return_value=None):
            assert sec_data.is_cache_stale("AAPL") is True

    def test_fresh_entry_not_stale(self):
        """Within TTL window: no submissions fetch, always fresh."""
        with patch("codes.data.sec_data.cache.read_entry", return_value=_FRESH_ENTRY):
            assert sec_data.is_cache_stale("AAPL") is False

    def test_legacy_entry_no_filing_date_is_stale(self):
        """Entry with no latest_filing key treated as stale."""
        entry = {"ts": time.time(), "data": _FAKE_FACTS}  # no latest_filing
        with patch("codes.data.sec_data.cache.read_entry", return_value=entry):
            assert sec_data.is_cache_stale("AAPL") is True

    def test_old_entry_same_filing_not_stale(self):
        """Beyond TTL but SEC reports same filing date → not stale."""
        with patch("codes.data.sec_data.cache.read_entry", return_value=_OLD_ENTRY), \
             patch("codes.data.sec_data.get_cik", return_value=("0000320193", "Apple")), \
             patch("codes.data.sec_data._fetch_submissions", return_value={}), \
             patch("codes.data.sec_data._latest_filing_date", return_value="2024-11-01"):
            assert sec_data.is_cache_stale("AAPL") is False

    def test_old_entry_newer_filing_is_stale(self):
        """Beyond TTL and SEC has a newer filing → stale."""
        with patch("codes.data.sec_data.cache.read_entry", return_value=_OLD_ENTRY), \
             patch("codes.data.sec_data.get_cik", return_value=("0000320193", "Apple")), \
             patch("codes.data.sec_data._fetch_submissions", return_value={}), \
             patch("codes.data.sec_data._latest_filing_date", return_value="2025-02-01"):
            assert sec_data.is_cache_stale("AAPL") is True

    def test_network_failure_returns_false(self):
        """If submissions fetch fails, assume cache is usable."""
        with patch("codes.data.sec_data.cache.read_entry", return_value=_OLD_ENTRY), \
             patch("codes.data.sec_data.get_cik", side_effect=Exception("network")):
            assert sec_data.is_cache_stale("AAPL") is False


# ══════════════════════════════════════════════════════════════════════════════
# refresh_if_needed
# ══════════════════════════════════════════════════════════════════════════════

class TestRefreshIfNeeded:
    def test_fresh_cache_no_fetch(self):
        """Cache is fresh → returns data without calling fetch_company_facts."""
        with patch("codes.data.sec_data.is_cache_stale", return_value=False), \
             patch("codes.data.sec_data.cache.read", return_value=_FAKE_FACTS), \
             patch("codes.data.sec_data.fetch_company_facts") as mock_fetch:
            result = sec_data.refresh_if_needed("AAPL")
            mock_fetch.assert_not_called()
            assert result == _FAKE_FACTS

    def test_stale_cache_triggers_fetch(self):
        """Cache is stale → fetch_company_facts is called."""
        with patch("codes.data.sec_data.is_cache_stale", return_value=True), \
             patch("codes.data.sec_data.fetch_company_facts", return_value=_FAKE_FACTS) as mock_fetch:
            result = sec_data.refresh_if_needed("AAPL")
            mock_fetch.assert_called_once_with("AAPL", include_delisted_warning=False)
            assert result == _FAKE_FACTS

    def test_fresh_but_cache_read_returns_none_triggers_fetch(self):
        """is_cache_stale=False but cache.read returns None → still fetches."""
        with patch("codes.data.sec_data.is_cache_stale", return_value=False), \
             patch("codes.data.sec_data.cache.read", return_value=None), \
             patch("codes.data.sec_data.fetch_company_facts", return_value=_FAKE_FACTS) as mock_fetch:
            result = sec_data.refresh_if_needed("AAPL")
            mock_fetch.assert_called_once()
            assert result == _FAKE_FACTS


# ══════════════════════════════════════════════════════════════════════════════
# get_financials
# ══════════════════════════════════════════════════════════════════════════════

class TestGetFinancials:
    def test_default_calls_refresh_if_needed(self):
        """Without force_refresh, delegates to refresh_if_needed."""
        with patch("codes.data.sec_data.refresh_if_needed", return_value=_FAKE_FACTS) as mock_r:
            result = sec_data.get_financials("AAPL")
            mock_r.assert_called_once_with("AAPL")
            assert result == _FAKE_FACTS

    def test_force_refresh_calls_fetch_directly(self):
        """force_refresh=True bypasses cache and calls fetch_company_facts."""
        with patch("codes.data.sec_data.fetch_company_facts", return_value=_FAKE_FACTS) as mock_f, \
             patch("codes.data.sec_data.refresh_if_needed") as mock_r:
            result = sec_data.get_financials("AAPL", force_refresh=True)
            mock_f.assert_called_once_with("AAPL", include_delisted_warning=False)
            mock_r.assert_not_called()
            assert result == _FAKE_FACTS

    def test_symbol_uppercased(self):
        """Ticker is normalised to uppercase before lookup."""
        with patch("codes.data.sec_data.refresh_if_needed", return_value=_FAKE_FACTS) as mock_r:
            sec_data.get_financials("aapl")
            mock_r.assert_called_once_with("AAPL")

    def test_force_refresh_symbol_uppercased(self):
        with patch("codes.data.sec_data.fetch_company_facts", return_value=_FAKE_FACTS) as mock_f:
            sec_data.get_financials("msft", force_refresh=True)
            mock_f.assert_called_once_with("MSFT", include_delisted_warning=False)


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
