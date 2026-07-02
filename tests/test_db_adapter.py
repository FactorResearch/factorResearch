import os
import tempfile
from pathlib import Path

import pytest

import codes.data.db as db


def test_sqlite_upsert_get_count_delete(tmp_path, monkeypatch):
    temp_db = tmp_path / "value_metrics.db"
    monkeypatch.setattr(db, "DB_PATH", temp_db)
    monkeypatch.setattr(db, "DB_URL", "")
    monkeypatch.setattr(db, "_initialized", False)

    db.init_db()
    db.upsert(
        "AAPL",
        market_cap=1_500_000.0,
        graham_number=120.0,
        buffett_iv=180.0,
        composite_score=75.0,
        verdict="BUY",
    )

    row = db.get("aapl")
    assert row is not None
    assert row["ticker"] == "AAPL"
    assert row["market_cap"] == 1_500_000.0
    assert row["graham_number"] == 120.0
    assert row["buffett_iv"] == 180.0
    assert row["composite_score"] == 75.0
    assert row["verdict"] == "BUY"

    assert db.count() == 1
    assert db.get_all("market_cap")[0]["ticker"] == "AAPL"

    db.delete("aapl")
    assert db.count() == 0


def test_get_all_order_by_safe(tmp_path, monkeypatch):
    temp_db = tmp_path / "value_metrics.db"
    monkeypatch.setattr(db, "DB_PATH", temp_db)
    monkeypatch.setattr(db, "DB_URL", "")
    monkeypatch.setattr(db, "_initialized", False)

    db.init_db()
    db.upsert("AAPL", market_cap=100.0, graham_number=1.0, buffett_iv=10.0, composite_score=10.0, verdict="BUY")
    db.upsert("MSFT", market_cap=200.0, graham_number=2.0, buffett_iv=20.0, composite_score=20.0, verdict="HOLD")

    rows = db.get_all("market_cap")
    assert [row["ticker"] for row in rows] == ["MSFT", "AAPL"]
    assert [row["ticker"] for row in db.get_all("ticker")] == ["AAPL", "MSFT"]


def test_postgres_flag_requires_psycopg(monkeypatch):
    monkeypatch.setattr(db, "DB_URL", "postgres://localhost/test")
    if db.psycopg is None:
        with pytest.raises(RuntimeError):
            db._pg_conn()
    else:
        pytest.skip("psycopg installed; Postgres connection test deferred")
