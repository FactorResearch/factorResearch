"""
Tests for codes/data/cache.py — encryption at rest.

security_audit_and_action_plan.md Phase 3 #13: portfolio holdings (names,
share counts) must be encrypted on disk. Market/reference data (sec_facts,
hist, analysis, etc.) is public and stays plaintext.
"""
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import json

import pytest


@pytest.fixture()
def cache_module(tmp_path, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY",
                        "yi1myb0TPr6CavFrLrf1lgV6MChXb5VSNK4FDqFpdlw=")
    monkeypatch.delenv("FLASK_ENV", raising=False)
    import codes.data.cache as cache

    cache.CACHE_DIR = tmp_path
    cache._encryptor = None
    return cache


def test_portfolio_kind_encrypted_on_disk(cache_module):
    cache_module.write("portfolio", "user1_p_growth", {
        "name": "Growth",
        "holdings": {"AAPL": {"shares": 10, "name": "Apple Inc."}},
    })
    raw = (cache_module.CACHE_DIR / "portfolio-user1_p_growth.json").read_text()
    assert "AAPL" not in raw
    assert "Apple" not in raw

    got = cache_module.read("portfolio", "user1_p_growth")
    assert got["holdings"]["AAPL"]["name"] == "Apple Inc."


def test_non_sensitive_kind_stays_plaintext(cache_module):
    cache_module.write("sec_facts", "aapl", {"name": "Apple Inc."})
    raw = (cache_module.CACHE_DIR / "sec_facts-aapl.json").read_text()
    assert "Apple Inc." in raw
    assert cache_module.read("sec_facts", "aapl") == {"name": "Apple Inc."}


def test_read_entry_decrypts_portfolio_kind(cache_module):
    cache_module.write("portfolio", "p2", {"name": "Value"}, latest_filing=None)
    entry = cache_module.read_entry("portfolio", "p2")
    assert entry["data"] == {"name": "Value"}
    assert entry["encrypted"] is True


def test_missing_key_falls_back_gracefully(cache_module, monkeypatch):
    """No ENCRYPTION_KEY + non-production: still writes/reads correctly
    (encrypted with an ephemeral session key rather than failing)."""
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    cache_module._encryptor = None
    cache_module.write("portfolio", "p3", {"name": "Ephemeral"})
    assert cache_module.read("portfolio", "p3") == {"name": "Ephemeral"}
