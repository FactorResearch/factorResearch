"""Regression tests for ISSUE_029 provider credential handling."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.data import api_fetcher


def test_placeholder_api_keys_are_not_treated_as_configured():
    assert api_fetcher._is_usable_api_key("") is False
    assert api_fetcher._is_usable_api_key(" your_api_key_here ") is False
    assert api_fetcher._is_usable_api_key("replace_me") is False
    assert api_fetcher._is_usable_api_key("real-provider-key") is True
