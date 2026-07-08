"""
Persistent value metrics store — Postgres only (market DB).

Per KNOWN_ISSUES ISSUE_002: this module owns the `factorresearch_market`
database exclusively. SQLite has been fully removed — there is no
fallback path anymore. DATABASE_MARKET_URL must be set or the app/worker
will fail to start.

Table: value_metrics
  ticker          TEXT PRIMARY KEY
  market_cap      REAL
  graham_number   REAL
  buffett_iv      REAL
  composite_score REAL
  verdict         TEXT
  updated_at      TEXT

Table: sec_facts
  ticker          TEXT PRIMARY KEY
  facts_json      TEXT
  latest_filing   TEXT
  updated_at      TEXT
"""

import os
import datetime
from contextlib import contextmanager
import json
from dotenv import load_dotenv
load_dotenv()
try:
    import psycopg
    from psycopg.rows import dict_row

except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None


_initialized = False

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sec_facts_meta (
    ticker        TEXT PRIMARY KEY,
    cik           TEXT,
    name          TEXT,
    sector        TEXT,
    sector_cls    TEXT,
    sic           INTEGER,
    filer_type    TEXT,
    latest_filing TEXT,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sec_facts_items (
    ticker   TEXT NOT NULL,
    concept  TEXT NOT NULL,   -- e.g. 'net_inc', 'equity', 'eps'
    year     INTEGER,
    value    DOUBLE PRECISION,
    end_date TEXT,
    PRIMARY KEY (ticker, concept, year)
);

CREATE INDEX IF NOT EXISTS idx_sec_facts_items_ticker ON sec_facts_items(ticker);

CREATE TABLE IF NOT EXISTS value_metrics (
    ticker          TEXT PRIMARY KEY,
    market_cap      REAL,
    graham_number   REAL,
    buffett_iv      REAL,
    composite_score REAL,
    verdict         TEXT,
    updated_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analysis_cache (
    ticker     TEXT PRIMARY KEY,
    data_json  TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

"""
_UPSERT_VALUE_METRICS = """
INSERT INTO value_metrics
    (ticker, market_cap, graham_number, buffett_iv, composite_score, verdict, updated_at)
VALUES (%(ticker)s, %(market_cap)s, %(graham_number)s, %(buffett_iv)s, %(composite_score)s, %(verdict)s, %(updated_at)s)
ON CONFLICT (ticker) DO UPDATE SET
    market_cap      = excluded.market_cap,
    graham_number   = excluded.graham_number,
    buffett_iv      = excluded.buffett_iv,
    composite_score = excluded.composite_score,
    verdict         = excluded.verdict,
    updated_at      = excluded.updated_at
"""

_SELECT_VALUE_METRICS = "SELECT * FROM value_metrics WHERE ticker = %(ticker)s"
_DELETE_VALUE_METRICS = "DELETE FROM value_metrics WHERE ticker = %(ticker)s"
_SCALAR_FIELDS = ("cik", "name", "sector", "sector_cls", "sic", "filer_type")

_UPSERT_META = """
INSERT INTO sec_facts_meta (ticker, cik, name, sector, sector_cls, sic, filer_type, latest_filing, updated_at)
VALUES (%(ticker)s, %(cik)s, %(name)s, %(sector)s, %(sector_cls)s, %(sic)s, %(filer_type)s, %(latest_filing)s, %(updated_at)s)
ON CONFLICT (ticker) DO UPDATE SET
    cik = excluded.cik, name = excluded.name, sector = excluded.sector,
    sector_cls = excluded.sector_cls, sic = excluded.sic, filer_type = excluded.filer_type,
    latest_filing = excluded.latest_filing, updated_at = excluded.updated_at
"""

_DELETE_ITEMS = "DELETE FROM sec_facts_items WHERE ticker = %(ticker)s"

_INSERT_ITEM = """
INSERT INTO sec_facts_items (ticker, concept, year, value, end_date)
VALUES (%(ticker)s, %(concept)s, %(year)s, %(value)s, %(end_date)s)
ON CONFLICT (ticker, concept, year) DO UPDATE SET
    value = excluded.value, end_date = excluded.end_date

"""
_UPSERT_ANALYSIS = """
INSERT INTO analysis_cache (ticker, data_json, updated_at)
VALUES (%(ticker)s, %(data_json)s, %(updated_at)s)
ON CONFLICT (ticker) DO UPDATE SET
    data_json  = excluded.data_json,
    updated_at = excluded.updated_at
"""
_SELECT_ANALYSIS = "SELECT data_json, updated_at FROM analysis_cache WHERE ticker = %(ticker)s"
_SELECT_ANALYSIS_TICKERS = "SELECT ticker FROM analysis_cache"
_SELECT_META = "SELECT * FROM sec_facts_meta WHERE ticker = %(ticker)s"
_SELECT_ITEMS = "SELECT concept, year, value, end_date FROM sec_facts_items WHERE ticker = %(ticker)s"


def upsert_analysis(ticker: str, data: dict) -> None:
    """Persist a full analyze_stock() result. Replaces cache.write('analysis', ...)."""
    _ensure_init()
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as con:
        con.execute(_UPSERT_ANALYSIS, {
            "ticker": ticker.upper(),
            "data_json": json.dumps(data, default=str),
            "updated_at": now,
        })


def get_analysis_entry(ticker: str) -> dict | None:
    """Return {'data': dict, 'updated_at': iso_str} or None."""
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        row = con.execute(_SELECT_ANALYSIS, {"ticker": ticker.upper()}).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["data_json"])
    except (TypeError, ValueError):
        return None
    return {"data": data, "updated_at": row["updated_at"]}


def get_analysis(ticker: str) -> dict | None:
    """Replaces cache.read('analysis', ticker)."""
    entry = get_analysis_entry(ticker)
    return entry["data"] if entry else None


def list_analysis_tickers() -> list[str]:
    """Replaces cache.list_cached_kind('analysis')."""
    _ensure_init()
    with _conn() as con:
        rows = con.execute(_SELECT_ANALYSIS_TICKERS).fetchall()
    return sorted(r[0] for r in rows)

def upsert_sec_facts(ticker: str, facts: dict, latest_filing: str | None) -> None:
    """
    Normalize the sec_facts dict into meta + item rows.
    Concepts are every key whose value is a list of {year|fy, value, end} records
    (i.e. everything except the scalar identification fields).
    """
    _ensure_init()
    t = ticker.upper()
    now = datetime.datetime.utcnow().isoformat()

    meta_params = {f: facts.get(f) for f in _SCALAR_FIELDS}
    meta_params.update({"ticker": t, "latest_filing": latest_filing, "updated_at": now})

    with _conn() as con:
        con.execute(_UPSERT_META, meta_params)
        con.execute(_DELETE_ITEMS, {"ticker": t})  # full replace — same semantics as old blob overwrite
        for concept, records in facts.items():
            if concept in _SCALAR_FIELDS or not isinstance(records, list):
                continue
            for r in records:
                year = r.get("year", r.get("fy"))
                if year is None:
                    continue
                con.execute(_INSERT_ITEM, {
                    "ticker": t, "concept": concept, "year": year,
                    "value": r.get("value"), "end_date": r.get("end"),
                })


def get_sec_facts(ticker: str) -> dict | None:
    """Reconstruct the sec_facts dict shape from normalized rows."""
    _ensure_init()
    t = ticker.upper()
    with _conn() as con:
        con.row_factory = dict_row
        meta = con.execute(_SELECT_META, {"ticker": t}).fetchone()
        if not meta:
            return None
        items = con.execute(_SELECT_ITEMS, {"ticker": t}).fetchall()

    result: dict = {f: meta.get(f) for f in _SCALAR_FIELDS}
    by_concept: dict[str, list] = {}
    for row in items:
        by_concept.setdefault(row["concept"], []).append({
            "year": row["year"], "value": row["value"], "end": row["end_date"],
        })
    for concept, recs in by_concept.items():
        result[concept] = sorted(recs, key=lambda r: r["year"] or 0, reverse=True)
    return result


def get_sec_facts_meta(ticker: str) -> dict | None:
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        row = con.execute(
            "SELECT ticker, latest_filing, updated_at FROM sec_facts_meta WHERE ticker = %(ticker)s",
            {"ticker": ticker.upper()},
        ).fetchone()
    return dict(row) if row else None


def _db_url() -> str:
    url = os.environ.get("DATABASE_MARKET_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_MARKET_URL is not set. SQLite has been removed — "
            "this module requires Postgres (factorresearch_market db). "
            "Set DATABASE_MARKET_URL to a valid Postgres connection string."
        )
    return url


def _pg_conn():
    import psycopg
    return psycopg.connect(_db_url())


@contextmanager
def _conn():
    """Yield a pooled Postgres connection (returned to the pool on exit)."""
    with _pg_conn() as con:
        yield con


def init_db() -> None:
    with _conn() as con:
        con.execute(_CREATE_TABLE)
        # con.execute(_CREATE_SEC_FACTS_TABLE)


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
    _ensure_init()
    now = datetime.datetime.utcnow().isoformat()
    params = {
        "ticker": ticker.upper(),
        "market_cap": market_cap,
        "graham_number": graham_number,
        "buffett_iv": buffett_iv,
        "composite_score": composite_score,
        "verdict": verdict,
        "updated_at": now,
    }
    with _conn() as con:
        con.execute(_UPSERT_VALUE_METRICS, params)


def get(ticker: str) -> dict | None:
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        row = con.execute(_SELECT_VALUE_METRICS, {"ticker": ticker.upper()}).fetchone()
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
        con.row_factory = dict_row
        rows = con.execute(
            f"SELECT * FROM value_metrics ORDER BY {col} IS NULL, {col} DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete(ticker: str) -> None:
    _ensure_init()
    with _conn() as con:
        con.execute(_DELETE_VALUE_METRICS, {"ticker": ticker.upper()})


def count() -> int:
    """Return total number of rows."""
    _ensure_init()
    with _conn() as con:
        return con.execute("SELECT COUNT(*) FROM value_metrics").fetchone()[0]