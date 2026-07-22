"""Dedicated analytics event store with optional separate database URL."""

from __future__ import annotations

import datetime as _dt
import json
import os
import threading
from contextlib import contextmanager

from dotenv import load_dotenv

from codes.core.db_pool import ConnectionPool
from codes.data import db
from codes.data.migrations import verify_migrations

load_dotenv()

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None


_initialized = False
_init_lock = threading.Lock()
_pool = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS analytics_events (
    id             BIGSERIAL PRIMARY KEY,
    occurred_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id        TEXT,
    anonymous_id   TEXT,
    event_name     TEXT NOT NULL,
    page_path      TEXT,
    metadata_json  JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_name_time
    ON analytics_events(event_name, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_events_user_time
    ON analytics_events(user_id, occurred_at DESC);
"""

_INSERT_EVENT = """
INSERT INTO analytics_events (
    occurred_at, user_id, anonymous_id, event_name, page_path, metadata_json
)
VALUES (
    %(occurred_at)s, %(user_id)s, %(anonymous_id)s, %(event_name)s, %(page_path)s, %(metadata_json)s::jsonb
)
"""

_SELECT_RECENT_EVENTS = """
SELECT occurred_at, user_id, anonymous_id, event_name, page_path, metadata_json
FROM analytics_events
ORDER BY occurred_at DESC
LIMIT %(limit)s
"""

_SELECT_EVENT_COUNTS = """
SELECT event_name, COUNT(*) AS event_count
FROM analytics_events
GROUP BY event_name
ORDER BY event_count DESC, event_name ASC
LIMIT %(limit)s
"""

_SELECT_TOP_METADATA_VALUES = """
SELECT
    metadata_json ->> %(metadata_key)s AS metadata_value,
    COUNT(*) AS event_count
FROM analytics_events
WHERE event_name = %(event_name)s
  AND COALESCE(metadata_json ->> %(metadata_key)s, '') <> ''
GROUP BY metadata_value
ORDER BY event_count DESC, metadata_value ASC
LIMIT %(limit)s
"""


def _db_url() -> str:
    url = os.environ.get("DATABASE_ANALYTICS_URL") or os.environ.get("DATABASE_MARKET_URL")
    if not url:
        raise RuntimeError("DATABASE_ANALYTICS_URL or DATABASE_MARKET_URL must be set.")
    return url


@contextmanager
def _conn():
    global _pool
    if psycopg is None:
        raise RuntimeError("psycopg is required for analytics event storage.")
    if _pool is None:
        url = _db_url()
        _pool = ConnectionPool(lambda: psycopg.connect(url), max_size=int(os.environ.get("ANALYTICS_DATABASE_POOL_SIZE", "2")))
    with _pool.connection() as con:
        yield con


def pool_health() -> dict:
    return _pool.stats() if _pool is not None else {"created": 0, "available": 0, "in_use": 0, "max_size": 2, "utilization": 0.0}


def ensure_schema() -> None:
    """Verify release-created analytics tables once per runtime process.

    Returns:
        None after the analytics migration scope passes read-only verification.

    Raises:
        Exception: Propagates missing, partial, unavailable, or checksum-drift
            state. Runtime analytics paths never create schema.

    Side Effects:
        Opens a read-only verification transaction on the first successful call.
    """
    global _initialized
    if _initialized:
        return
    db.verify_runtime_credential_boundary()
    with _init_lock:
        if _initialized:
            return
        with _conn() as con:
            verify_migrations(con, "analytics", required_tables=("analytics_events",))
        _initialized = True


def insert_event(*, user_id: str | None, anonymous_id: str | None, event_name: str,
                 page_path: str | None, metadata: dict | None) -> None:
    ensure_schema()
    payload = {
        "occurred_at": _dt.datetime.now(_dt.UTC),
        "user_id": user_id,
        "anonymous_id": anonymous_id,
        "event_name": event_name,
        "page_path": page_path,
        "metadata_json": json.dumps(metadata or {}, default=str),
    }
    with _conn() as con:
        con.execute(_INSERT_EVENT, payload)


def delete_identity_events(identity: str) -> int:
    ensure_schema()
    with _conn() as con:
        result = con.execute(
            "DELETE FROM analytics_events WHERE user_id = %(identity)s OR anonymous_id = %(identity)s",
            {"identity": identity},
        )
    return result.rowcount


def list_recent_events(limit: int = 50) -> list[dict]:
    ensure_schema()
    with _conn() as con:
        con.row_factory = dict_row
        rows = con.execute(_SELECT_RECENT_EVENTS, {"limit": max(int(limit or 0), 1)}).fetchall()
    return [dict(row) for row in rows]


def get_event_counts(limit: int = 50) -> list[dict]:
    ensure_schema()
    with _conn() as con:
        con.row_factory = dict_row
        rows = con.execute(_SELECT_EVENT_COUNTS, {"limit": max(int(limit or 0), 1)}).fetchall()
    return [dict(row) for row in rows]


def get_top_metadata_values(event_name: str, metadata_key: str, limit: int = 20) -> list[dict]:
    if not event_name or not metadata_key:
        return []
    ensure_schema()
    with _conn() as con:
        con.row_factory = dict_row
        rows = con.execute(
            _SELECT_TOP_METADATA_VALUES,
            {
                "event_name": event_name,
                "metadata_key": metadata_key,
                "limit": max(int(limit or 0), 1),
            },
        ).fetchall()
    return [dict(row) for row in rows]
