"""Dedicated analytics event store with optional separate database URL."""

from __future__ import annotations

from contextlib import contextmanager
import datetime as _dt
import json
import os

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


def _db_url() -> str:
    url = os.environ.get("DATABASE_ANALYTICS_URL") or os.environ.get("DATABASE_MARKET_URL")
    if not url:
        raise RuntimeError("DATABASE_ANALYTICS_URL or DATABASE_MARKET_URL must be set.")
    return url


@contextmanager
def _conn():
    if psycopg is None:
        raise RuntimeError("psycopg is required for analytics event storage.")
    con = psycopg.connect(_db_url())
    try:
        yield con
        con.commit()
    finally:
        con.close()


def ensure_schema() -> None:
    global _initialized
    if _initialized:
        return
    with _conn() as con:
        con.execute(_CREATE_TABLE)
    _initialized = True


def insert_event(*, user_id: str | None, anonymous_id: str | None, event_name: str,
                 page_path: str | None, metadata: dict | None) -> None:
    ensure_schema()
    payload = {
        "occurred_at": _dt.datetime.now(_dt.timezone.utc),
        "user_id": user_id,
        "anonymous_id": anonymous_id,
        "event_name": event_name,
        "page_path": page_path,
        "metadata_json": json.dumps(metadata or {}, default=str),
    }
    with _conn() as con:
        con.execute(_INSERT_EVENT, payload)

