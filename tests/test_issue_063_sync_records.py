"""Acceptance coverage for ISSUE_063 synchronization-ready user records."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from codes import portfolio
from codes.data import cache, db
from codes.services import user_settings


@pytest.fixture()
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "yi1myb0TPr6CavFrLrf1lgV6MChXb5VSNK4FDqFpdlw=")
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache._encryptor = None
    yield
    cache._encryptor = None


def test_portfolio_tombstone_is_syncable_restorable_and_versioned(isolated_cache) -> None:
    created = portfolio.create_portfolio("user-1", "Core")
    original_version = created["version"]

    portfolio.delete_portfolio("user-1", "Core")

    assert portfolio.list_portfolios("user-1") == []
    tombstone = portfolio.list_portfolio_changes("user-1")[0]
    assert tombstone["deleted_at"]
    assert tombstone["version"] == original_version + 1

    restored = portfolio.restore_portfolio(
        "user-1", created["id"], expected_version=tombstone["version"]
    )
    assert restored["deleted_at"] is None
    assert portfolio.list_portfolios("user-1") == ["Core"]


def test_stale_portfolio_write_is_rejected(isolated_cache) -> None:
    stale = dict(portfolio.create_portfolio("user-1", "Core"))
    current = portfolio.load_portfolio("user-1", "Core")
    current["name"] = "Current"
    portfolio.save_portfolio("user-1", current)

    stale["name"] = "Stale"
    with pytest.raises(RuntimeError, match="version conflict"):
        portfolio.save_portfolio("user-1", stale)


def test_saved_screener_deletion_keeps_a_sync_tombstone(monkeypatch) -> None:
    stored = {}
    monkeypatch.setattr(user_settings.db, "get_user_settings", lambda _user_id: stored)
    monkeypatch.setattr(
        user_settings.db,
        "upsert_user_settings",
        lambda _user_id, settings: stored.update(settings) or settings,
    )
    active = user_settings.add_saved_screener(
        "user-1", name="Value", market="US", sector="", indexes=[]
    )["saved_screeners"][0]

    visible = user_settings.delete_saved_screener("user-1", active["id"])
    changes = user_settings.get_user_settings("user-1", include_deleted=True)

    assert visible["saved_screeners"] == []
    assert changes["saved_screeners"][0]["deleted_at"]
    assert changes["saved_screeners"][0]["version"] == active["version"] + 1


class _Result:
    def fetchone(self):
        return None


class _Connection:
    row_factory = None

    def execute(self, _sql, _params):
        return _Result()


@contextmanager
def _connection():
    yield _Connection()


def test_settings_database_rejects_a_stale_version(monkeypatch) -> None:
    monkeypatch.setattr(db, "_users_initialized", True)
    monkeypatch.setattr(db, "_users_conn", _connection)

    with pytest.raises(RuntimeError, match="version conflict"):
        db.upsert_user_settings("user-1", {"_sync": {"version": 2}})
