"""
Persistent value metrics store — SQLite or Postgres.

Survives process restarts; complements the JSON file cache with a
queryable store that supports ordering by market cap.

Table: value_metrics
  ticker          TEXT PRIMARY KEY
  market_cap      REAL   -- price × shares in $M (for size ordering)
  graham_number   REAL   -- Graham Number (√(22.5 × EPS × BVPS))
  buffett_iv      REAL   -- Buffett two-stage DCF intrinsic value
  composite_score REAL   -- latest enhanced composite score (0-100)
  verdict         TEXT   -- STRONG BUY / BUY / WATCH / HOLD/WEAK / AVOID
  updated_at      TEXT   -- ISO-8601 UTC timestamp of last write
"""

import os
import sqlite3
import datetime
from contextlib import contextmanager
from pathlib import Path
import json 

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.pool import ConnectionPool
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None
    ConnectionPool = None

def _db_url():
    return os.environ.get("DATABASE_MARKET_URL")

DB_PATH = Path(".cache") / "value_metrics.db"
_PG_POOL = None
_initialized = False

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS value_metrics (
    ticker          TEXT PRIMARY KEY,
    market_cap      REAL,
    graham_number   REAL,
    buffett_iv      REAL,
    composite_score REAL,
    verdict         TEXT,
    updated_at      TEXT NOT NULL
)
"""
_CREATE_SEC_FACTS_TABLE = """
CREATE TABLE IF NOT EXISTS sec_facts (
    ticker          TEXT PRIMARY KEY,
    facts_json      TEXT NOT NULL,
    latest_filing   TEXT,
    updated_at      TEXT NOT NULL
)
"""

_UPSERT_SEC_FACTS_SQLITE = """
INSERT INTO sec_facts (ticker, facts_json, latest_filing, updated_at)
VALUES (?, ?, ?, ?)
ON CONFLICT(ticker) DO UPDATE SET
    facts_json    = excluded.facts_json,
    latest_filing = excluded.latest_filing,
    updated_at    = excluded.updated_at
"""

_UPSERT_SEC_FACTS_POSTGRES = """
INSERT INTO sec_facts (ticker, facts_json, latest_filing, updated_at)
VALUES (%s, %s, %s, %s)
ON CONFLICT(ticker) DO UPDATE SET
    facts_json    = excluded.facts_json,
    latest_filing = excluded.latest_filing,
    updated_at    = excluded.updated_at
"""

_SELECT_SEC_FACTS_SQLITE = "SELECT * FROM sec_facts WHERE ticker = ?"
_SELECT_SEC_FACTS_POSTGRES = "SELECT * FROM sec_facts WHERE ticker = %s"

_UPSERT_SQLITE = """
INSERT INTO value_metrics
    (ticker, market_cap, graham_number, buffett_iv, composite_score, verdict, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(ticker) DO UPDATE SET
    market_cap      = excluded.market_cap,
    graham_number   = excluded.graham_number,
    buffett_iv      = excluded.buffett_iv,
    composite_score = excluded.composite_score,
    verdict         = excluded.verdict,
    updated_at      = excluded.updated_at
"""

_UPSERT_POSTGRES = """
INSERT INTO value_metrics
    (ticker, market_cap, graham_number, buffett_iv, composite_score, verdict, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT(ticker) DO UPDATE SET
    market_cap      = excluded.market_cap,
    graham_number   = excluded.graham_number,
    buffett_iv      = excluded.buffett_iv,
    composite_score = excluded.composite_score,
    verdict         = excluded.verdict,
    updated_at      = excluded.updated_at
"""

_SELECT_SQLITE = "SELECT * FROM value_metrics WHERE ticker = ?"
_SELECT_POSTGRES = "SELECT * FROM value_metrics WHERE ticker = %s"

_DELETE_SQLITE = "DELETE FROM value_metrics WHERE ticker = ?"
_DELETE_POSTGRES = "DELETE FROM value_metrics WHERE ticker = %s"

_COUNT_SQLITE = "SELECT COUNT(*) FROM value_metrics"
_COUNT_POSTGRES = "SELECT COUNT(*) FROM value_metrics"


def _using_postgres() -> bool:
    return bool(_db_url())


def _sqlite_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def _pg_conn():
    global _PG_POOL
    DB_URL = _db_url()
    if psycopg is None:
        raise RuntimeError(
            "Postgres support requires psycopg[binary]. Install it or unset DATABASE_URL."
        )
    if _PG_POOL is None:
        _PG_POOL = ConnectionPool(DB_URL, min_size=1, max_size=5)
    return _PG_POOL.connection()


@contextmanager
def _conn():
    """
    Context manager yielding a DB connection.

    Postgres: delegates to the pool's own connection() context manager,
    which returns (not closes) the connection to the pool on exit.

    SQLite: sqlite3.Connection acting as its own context manager commits/
    rolls back on exit but does NOT close the handle — under concurrent
    multi-user request volume (ISSUE_007) this leaks file descriptors.
    Explicitly close it here so the fallback path is safe even before a
    DATABASE_URL is configured.
    """
    
    if _using_postgres():
        with _pg_conn() as con:
            yield con
    else:
        con = _sqlite_conn()
        try:
            with con:
                yield con
        finally:
            con.close()


def init_db() -> None:
    with _conn() as con:
        con.execute(_CREATE_TABLE)
        con.execute(_CREATE_SEC_FACTS_TABLE)

    if _using_postgres():
        _migrate_sqlite_to_postgres()


def _migrate_sqlite_to_postgres() -> None:
    if not DB_PATH.exists():
        return

    try:
        with _sqlite_conn() as sqlite_con:
            sqlite_con.row_factory = sqlite3.Row
            old_rows = sqlite_con.execute("SELECT * FROM value_metrics").fetchall()
    except Exception:
        return

    if not old_rows:
        return

    with _pg_conn() as pg_con:
        for row in old_rows:
            pg_con.execute(
                _UPSERT_POSTGRES,
                (
                    row["ticker"],
                    row["market_cap"],
                    row["graham_number"],
                    row["buffett_iv"],
                    row["composite_score"],
                    row["verdict"],
                    row["updated_at"],
                ),
            )


def _ensure_init() -> None:
    global _initialized
    if not _initialized:
        init_db()
        _initialized = True


def upsert(
    ticker: str,
    *,
    market_cap: float | None = None,
    graham_number: float | None = None,
    buffett_iv: float | None = None,
    composite_score: float | None = None,
    verdict: str | None = None,
) -> None:
    """Insert or update a ticker's value metrics row."""
    _ensure_init()
    now = datetime.datetime.utcnow().isoformat()
    params = (
        ticker.upper(),
        market_cap,
        graham_number,
        buffett_iv,
        composite_score,
        verdict,
        now,
    )
    try:
        with _conn() as con:
            con.execute(
                _UPSERT_POSTGRES if _using_postgres() else _UPSERT_SQLITE,
                params,
            )
    except Exception as e:
        print(f"  [DB] upsert failed for {ticker}: {e}")


def get(ticker: str) -> dict | None:
    """Return a single ticker's row, or None if absent."""
    _ensure_init()
    with _conn() as con:
        if _using_postgres():
            con.row_factory = dict_row
            row = con.execute(_SELECT_POSTGRES, (ticker.upper(),)).fetchone()
        else:
            con.row_factory = sqlite3.Row
            row = con.execute(_SELECT_SQLITE, (ticker.upper(),)).fetchone()
    return dict(row) if row else None


def get_all(order_by: str = "market_cap") -> list[dict]:
    """
    Return all rows ordered by `order_by` descending, NULLs last.

    order_by must be one of the allowed column names to prevent injection.
    """
    _safe_cols = {
        "market_cap", "composite_score", "graham_number",
        "buffett_iv", "updated_at", "ticker",
    }
    col = order_by if order_by in _safe_cols else "market_cap"
    _ensure_init()
    with _conn() as con:
        if _using_postgres():
            con.row_factory = dict_row
        else:
            con.row_factory = sqlite3.Row
        rows = con.execute(
            f"SELECT * FROM value_metrics ORDER BY {col} IS NULL, {col} DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete(ticker: str) -> None:
    """Remove a ticker's row (e.g. when a portfolio holding is deleted)."""
    _ensure_init()
    with _conn() as con:
        con.execute(
            _DELETE_POSTGRES if _using_postgres() else _DELETE_SQLITE,
            (ticker.upper(),),
        )


def count() -> int:
    """Return total number of rows."""
    _ensure_init()
    with _conn() as con:
        return con.execute("SELECT COUNT(*) FROM value_metrics").fetchone()[0]
def upsert_sec_facts(ticker: str, facts: dict, latest_filing: str | None) -> None:
    """Store the full sec_facts blob for a ticker (worker-only write path)."""
    _ensure_init()
    now = datetime.datetime.utcnow().isoformat()
    facts_json = json.dumps(facts)
    params = (ticker.upper(), facts_json, latest_filing, now)
    try:
        with _conn() as con:
            con.execute(
                _UPSERT_SEC_FACTS_POSTGRES if _using_postgres() else _UPSERT_SEC_FACTS_SQLITE,
                params,
            )
    except Exception as e:
        print(f"  [DB] upsert_sec_facts failed for {ticker}: {e}")


def get_sec_facts(ticker: str) -> dict | None:
    """Return the parsed sec_facts blob for a ticker, or None if absent."""
    _ensure_init()
    with _conn() as con:
        if _using_postgres():
            con.row_factory = dict_row
            row = con.execute(_SELECT_SEC_FACTS_POSTGRES, (ticker.upper(),)).fetchone()
        else:
            con.row_factory = sqlite3.Row
            row = con.execute(_SELECT_SEC_FACTS_SQLITE, (ticker.upper(),)).fetchone()
    if not row:
        return None
    row = dict(row)
    try:
        return json.loads(row["facts_json"])
    except (TypeError, ValueError):
        return None


def get_sec_facts_meta(ticker: str) -> dict | None:
    """Return only {ticker, latest_filing, updated_at} — cheap staleness check, no blob parse."""
    _ensure_init()
    with _conn() as con:
        if _using_postgres():
            con.row_factory = dict_row
            row = con.execute(
                "SELECT ticker, latest_filing, updated_at FROM sec_facts WHERE ticker = %s",
                (ticker.upper(),),
            ).fetchone()
        else:
            con.row_factory = sqlite3.Row
            row = con.execute(
                "SELECT ticker, latest_filing, updated_at FROM sec_facts WHERE ticker = ?",
                (ticker.upper(),),
            ).fetchone()
    return dict(row) if row else None