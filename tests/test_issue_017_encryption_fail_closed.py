import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _reset_cache(tmp_path, monkeypatch):
    import codes.data.cache as cache

    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache._encryptor = None
    return cache


def test_production_missing_encryption_key_does_not_write_plaintext(tmp_path, monkeypatch):
    cache = _reset_cache(tmp_path, monkeypatch)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

    payload = {"name": "Retirement", "holdings": {"AAPL": {"shares": 10}}}

    assert cache.write("portfolio", "user1_p_retirement", payload) is False
    assert not (tmp_path / "portfolio-user1_p_retirement.json").exists()


def test_production_invalid_encryption_key_does_not_write_plaintext(tmp_path, monkeypatch):
    cache = _reset_cache(tmp_path, monkeypatch)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("ENCRYPTION_KEY", "not-a-fernet-key")

    payload = {"name": "Growth", "holdings": {"MSFT": {"shares": 7}}}

    assert cache.write("portfolio", "user1_p_growth", payload) is False
    assert not (tmp_path / "portfolio-user1_p_growth.json").exists()


def test_production_missing_encryption_key_allows_non_sensitive_cache(tmp_path, monkeypatch):
    cache = _reset_cache(tmp_path, monkeypatch)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

    payload = {"name": "Apple Inc."}

    assert cache.write("sec_facts", "aapl", payload) is True
    raw = (tmp_path / "sec_facts-aapl.json").read_text()
    assert "Apple Inc." in raw
    assert cache.read("sec_facts", "aapl") == payload
