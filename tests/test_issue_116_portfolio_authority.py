"""Fast acceptance coverage for ISSUE_116's storage boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from codes import portfolio
from codes.data import cache, portfolio_repository


def test_migration_defines_normalized_forced_rls_schema() -> None:
    sql = Path("migrations/003_issue_116_portfolio_authority_users.sql").read_text()

    for table in (
        "portfolios",
        "portfolio_holdings",
        "portfolio_transactions",
        "portfolio_tombstones",
        "portfolio_simulation_results",
        "portfolio_legacy_imports",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
    assert "current_setting('app.user_id', true)" in sql
    assert "REVOKE ALL ON portfolios" in sql
    assert "FOREIGN KEY (portfolio_id, owner_id)" in sql


def test_simulation_cache_payloads_are_encrypted(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    cache._encryptor = None

    assert cache.write("port_sim", "safe", {"holdings": {"AAPL": {"shares": 5}}})

    raw = (tmp_path / "port_sim-safe.json").read_text()
    assert '"encrypted": true' in raw
    assert "AAPL" not in raw
    assert cache.read("port_sim", "safe")["holdings"]["AAPL"]["shares"] == 5
    cache._encryptor = None


def test_production_rejects_file_portfolio_authority(monkeypatch) -> None:
    monkeypatch.setattr(portfolio_repository, "is_production", lambda: True)
    monkeypatch.setenv("PORTFOLIO_STORAGE_BACKEND", "cache")

    with pytest.raises(RuntimeError, match="cannot use local cache"):
        portfolio_repository.is_enabled()


def test_postgres_adapter_routes_without_writing_local_holdings(monkeypatch) -> None:
    expected = {"id": "a" * 32, "name": "Core", "version": 1, "holdings": {}}
    monkeypatch.setattr(portfolio_repository, "is_enabled", lambda: True)
    monkeypatch.setattr(
        portfolio_repository, "load_portfolio", lambda user_id, name: dict(expected)
    )
    monkeypatch.setattr(
        portfolio.cache,
        "read",
        lambda *_args, **_kwargs: pytest.fail("PostgreSQL reads must not touch cache"),
    )

    assert portfolio.load_portfolio("user-1", "Core") == expected


def test_legacy_erasure_discovers_orphaned_hashed_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("PORTFOLIO_STORAGE_BACKEND", "cache")
    cache._encryptor = None
    user_id = "auth0|orphan"
    orphan_key = portfolio._portfolio_key(user_id, "b" * 32)
    assert cache.write(
        "portfolio", orphan_key, {"name": "Deleted", "holdings": {}, "deleted_at": "now"}
    )
    assert cache.write("port_sim", portfolio._simulation_key(user_id, "Deleted"), {"holdings": {}})

    evidence = portfolio._erase_legacy_user_files(user_id)

    assert evidence == {"portfolio_files": 1, "simulation_files": 1}
    assert cache.list_keys("portfolio") == []
    assert cache.list_keys("port_sim") == []
    cache._encryptor = None
