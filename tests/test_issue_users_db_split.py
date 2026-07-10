import os
import sys
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.data import db


class _FakeResult:
    def __init__(self, rows=None, row=None):
        self._rows = rows or []
        self._row = row

    def fetchall(self):
        return self._rows

    def fetchone(self):
        if self._row is not None:
            return self._row
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, tag, row=None, rows=None):
        self.tag = tag
        self.row_factory = None
        self.calls = []
        self._row = row
        self._rows = rows or []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return _FakeResult(rows=self._rows, row=self._row)


@contextmanager
def _ctx(conn):
    yield conn


def test_users_db_url_prefers_dedicated_env(monkeypatch):
    monkeypatch.setenv("DATABASE_MARKET_URL", "postgres://market")
    monkeypatch.setenv("DATABASE_USERS_URL", "postgres://users")

    assert db._users_db_url() == "postgres://users"


def test_user_weights_use_users_connection(monkeypatch):
    users_conn = _FakeConn("users", rows=[{"factor_name": "quality", "weight": 0.5}])
    market_conn = _FakeConn("market")

    monkeypatch.setattr(db, "_users_initialized", True)
    monkeypatch.setattr(db, "_market_initialized", True)
    monkeypatch.setattr(db, "_users_conn", lambda: _ctx(users_conn))
    monkeypatch.setattr(db, "_conn", lambda: _ctx(market_conn))

    result = db.get_user_weights("u1")

    assert result == {"quality": 0.5}
    assert len(users_conn.calls) == 1
    assert len(market_conn.calls) == 0


def test_subscription_lookup_uses_users_connection(monkeypatch):
    users_conn = _FakeConn("users", row={"user_id": "u1", "plan": "premium", "status": "active"})
    market_conn = _FakeConn("market")

    monkeypatch.setattr(db, "_users_initialized", True)
    monkeypatch.setattr(db, "_market_initialized", True)
    monkeypatch.setattr(db, "_users_conn", lambda: _ctx(users_conn))
    monkeypatch.setattr(db, "_conn", lambda: _ctx(market_conn))

    result = db.get_subscription("u1")

    assert result["plan"] == "premium"
    assert len(users_conn.calls) == 1
    assert len(market_conn.calls) == 0


def test_market_data_stays_on_market_connection(monkeypatch):
    users_conn = _FakeConn("users")
    market_conn = _FakeConn("market", row={"ticker": "AAPL", "market_cap": 1})

    monkeypatch.setattr(db, "_users_initialized", True)
    monkeypatch.setattr(db, "_market_initialized", True)
    monkeypatch.setattr(db, "_users_conn", lambda: _ctx(users_conn))
    monkeypatch.setattr(db, "_conn", lambda: _ctx(market_conn))

    result = db.get("AAPL")

    assert result["ticker"] == "AAPL"
    assert len(market_conn.calls) == 1
    assert len(users_conn.calls) == 0
