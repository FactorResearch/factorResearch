"""Provider-neutral point-in-time market-data repository."""

from __future__ import annotations

import datetime as dt
import threading
import uuid
from dataclasses import asdict, dataclass

from psycopg.rows import dict_row

from codes.data import db

_initialized = False
_init_lock = threading.Lock()


SCHEMA = """
CREATE TABLE IF NOT EXISTS security_entities (
    entity_id UUID PRIMARY KEY, legal_name TEXT NOT NULL, country TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS securities (
    security_id UUID PRIMARY KEY, entity_id UUID NOT NULL REFERENCES security_entities(entity_id),
    security_type TEXT NOT NULL DEFAULT 'equity', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS security_listings (
    listing_id UUID PRIMARY KEY, security_id UUID NOT NULL REFERENCES securities(security_id),
    market_code TEXT NOT NULL, exchange_code TEXT NOT NULL DEFAULT '', currency TEXT,
    valid_from DATE NOT NULL, valid_to DATE, status TEXT NOT NULL DEFAULT 'active',
    UNIQUE (security_id, market_code, exchange_code, valid_from)
);
CREATE TABLE IF NOT EXISTS security_identifiers (
    security_id UUID NOT NULL REFERENCES securities(security_id), namespace TEXT NOT NULL,
    identifier TEXT NOT NULL, scope TEXT NOT NULL DEFAULT 'GLOBAL', valid_from DATE NOT NULL, valid_to DATE,
    source TEXT NOT NULL, confidence TEXT NOT NULL, observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (namespace, identifier, scope, valid_from)
);
CREATE INDEX IF NOT EXISTS idx_security_identifiers_security ON security_identifiers(security_id);

CREATE TABLE IF NOT EXISTS filing_versions (
    filing_id UUID PRIMARY KEY, security_id UUID NOT NULL REFERENCES securities(security_id),
    document_id TEXT NOT NULL, form_type TEXT, period_end DATE, filed_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ, source TEXT NOT NULL, source_url TEXT, content_hash TEXT,
    supersedes_id UUID REFERENCES filing_versions(filing_id), ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (security_id, source, document_id)
);
CREATE INDEX IF NOT EXISTS idx_filing_versions_asof ON filing_versions(security_id, filed_at DESC);
CREATE TABLE IF NOT EXISTS point_in_time_facts (
    fact_id BIGSERIAL PRIMARY KEY, filing_id UUID NOT NULL REFERENCES filing_versions(filing_id),
    security_id UUID NOT NULL REFERENCES securities(security_id), statement_type TEXT NOT NULL,
    fact_name TEXT NOT NULL, period_start DATE, period_end DATE NOT NULL, fiscal_year INTEGER,
    fiscal_period TEXT, value DOUBLE PRECISION NOT NULL, unit TEXT NOT NULL, currency TEXT,
    available_at TIMESTAMPTZ NOT NULL, system_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    system_to TIMESTAMPTZ, confidence TEXT NOT NULL, UNIQUE (filing_id, statement_type, fact_name, period_end, unit)
);
CREATE INDEX IF NOT EXISTS idx_pit_facts_lookup
    ON point_in_time_facts(security_id, fact_name, period_end DESC, available_at DESC);

CREATE TABLE IF NOT EXISTS corporate_actions (
    action_id UUID PRIMARY KEY, security_id UUID NOT NULL REFERENCES securities(security_id),
    action_type TEXT NOT NULL, provider_event_id TEXT NOT NULL, announced_at TIMESTAMPTZ,
    effective_date DATE NOT NULL, ex_date DATE, record_date DATE, payment_date DATE,
    ratio DOUBLE PRECISION, amount DOUBLE PRECISION, currency TEXT, source TEXT NOT NULL,
    source_url TEXT, version INTEGER NOT NULL DEFAULT 1, ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, provider_event_id, version)
);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_security_date ON corporate_actions(security_id, effective_date);
CREATE TABLE IF NOT EXISTS daily_prices (
    security_id UUID NOT NULL REFERENCES securities(security_id), price_date DATE NOT NULL,
    open DOUBLE PRECISION, high DOUBLE PRECISION, low DOUBLE PRECISION, close DOUBLE PRECISION NOT NULL,
    adjusted_close DOUBLE PRECISION, volume DOUBLE PRECISION, currency TEXT NOT NULL,
    adjustment_version TEXT, source TEXT NOT NULL, observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (security_id, price_date, source)
);
CREATE TABLE IF NOT EXISTS fx_rates (
    base_currency TEXT NOT NULL, quote_currency TEXT NOT NULL, rate_date DATE NOT NULL,
    rate DOUBLE PRECISION NOT NULL CHECK (rate > 0), source TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (base_currency, quote_currency, rate_date, source)
);
CREATE TABLE IF NOT EXISTS market_universes (
    universe_id UUID PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    market_code TEXT, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS universe_memberships (
    universe_id UUID NOT NULL REFERENCES market_universes(universe_id),
    security_id UUID NOT NULL REFERENCES securities(security_id), valid_from DATE NOT NULL,
    valid_to DATE, source TEXT NOT NULL, observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (universe_id, security_id, valid_from)
);
CREATE TABLE IF NOT EXISTS track_e_ingestion_checkpoints (
    dataset TEXT NOT NULL, item_key TEXT NOT NULL, status TEXT NOT NULL,
    rows_written INTEGER NOT NULL DEFAULT 0, error TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ,
    PRIMARY KEY (dataset, item_key)
);
"""


@dataclass(frozen=True)
class SecurityIdentity:
    security_id: str
    entity_id: str
    legal_name: str
    symbol: str
    market_code: str
    exchange_code: str | None = None
    currency: str | None = None


def ensure_schema() -> None:
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        with db._conn() as con:
            con.execute(SCHEMA)
        _initialized = True


def register_security(identity: SecurityIdentity, *, source: str, confidence: str = "provider_normalized_internal_only") -> str:
    """Idempotently register an entity, security, listing, and symbol."""
    ensure_schema()
    values = {**asdict(identity), "exchange_code": identity.exchange_code or ""}
    values.update(source=source, confidence=confidence, valid_from=dt.date(1900, 1, 1))
    with db._conn() as con:
        con.execute("INSERT INTO security_entities (entity_id, legal_name) VALUES (%(entity_id)s, %(legal_name)s) ON CONFLICT (entity_id) DO UPDATE SET legal_name=excluded.legal_name", values)
        con.execute("INSERT INTO securities (security_id, entity_id) VALUES (%(security_id)s, %(entity_id)s) ON CONFLICT (security_id) DO NOTHING", values)
        con.execute("""INSERT INTO security_listings (listing_id, security_id, market_code, exchange_code, currency, valid_from)
                       VALUES (%(listing_id)s, %(security_id)s, %(market_code)s, %(exchange_code)s, %(currency)s, %(valid_from)s)
                       ON CONFLICT (security_id, market_code, exchange_code, valid_from) DO NOTHING""", {**values, "listing_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"listing:{identity.security_id}:{identity.market_code}:{identity.exchange_code}"))})
        con.execute("""INSERT INTO security_identifiers (security_id, namespace, identifier, scope, valid_from, source, confidence)
                       VALUES (%(security_id)s, 'TICKER', %(symbol)s, %(market_code)s, %(valid_from)s, %(source)s, %(confidence)s)
                       ON CONFLICT (namespace, identifier, scope, valid_from) DO UPDATE SET security_id=excluded.security_id, source=excluded.source, confidence=excluded.confidence""", values)
    return identity.security_id


def add_identifier(security_id: str, namespace: str, identifier: str, *, source: str, scope: str = "GLOBAL", valid_from: dt.date | None = None, valid_to: dt.date | None = None, confidence: str = "provider_normalized_internal_only") -> None:
    if not identifier:
        return
    ensure_schema()
    with db._conn() as con:
        con.execute("""INSERT INTO security_identifiers (security_id, namespace, identifier, scope, valid_from, valid_to, source, confidence)
                       VALUES (%(security_id)s, %(namespace)s, %(identifier)s, %(scope)s, %(valid_from)s, %(valid_to)s, %(source)s, %(confidence)s)
                       ON CONFLICT (namespace, identifier, scope, valid_from) DO UPDATE SET security_id=excluded.security_id, valid_to=excluded.valid_to, source=excluded.source, confidence=excluded.confidence""",
                    {"security_id": security_id, "namespace": namespace.upper(), "identifier": identifier.upper(), "scope": scope.upper(), "valid_from": valid_from or dt.date(1900, 1, 1), "valid_to": valid_to, "source": source, "confidence": confidence})


def resolve_security(namespace: str, identifier: str, as_of: dt.date | None = None, *, market_code: str | None = None) -> dict | None:
    ensure_schema()
    date = as_of or dt.date.today()
    with db._conn() as con:
        con.row_factory = dict_row
        row = con.execute("""SELECT i.security_id::text, i.namespace, i.identifier, e.legal_name,
                                    l.market_code, l.exchange_code, l.currency, l.status
                             FROM security_identifiers i JOIN securities s USING (security_id)
                             JOIN security_entities e USING (entity_id)
                             LEFT JOIN LATERAL (
                                 SELECT listing.* FROM security_listings listing
                                 WHERE listing.security_id=i.security_id
                                 ORDER BY CASE WHEN listing.valid_from <= %(as_of)s AND (listing.valid_to IS NULL OR listing.valid_to >= %(as_of)s) THEN 0 ELSE 1 END,
                                          listing.valid_from DESC LIMIT 1
                             ) l ON TRUE
                             WHERE i.namespace=%(namespace)s AND i.identifier=%(identifier)s
                               AND (%(market_code)s IS NULL OR i.scope=%(market_code)s)
                               AND i.valid_from <= %(as_of)s AND (i.valid_to IS NULL OR i.valid_to >= %(as_of)s)
                             ORDER BY i.valid_from DESC LIMIT 1""",
                          {"namespace": namespace.upper(), "identifier": identifier.upper(), "as_of": date, "market_code": market_code.upper() if market_code else None}).fetchone()
    return dict(row) if row else None


def record_symbol_change(security_id: str, old_symbol: str, new_symbol: str, effective_date: dt.date, *, market_code: str, source: str) -> None:
    """Close the old ticker interval and open the replacement on one security."""
    ensure_schema()
    with db._conn() as con:
        con.execute("""UPDATE security_identifiers SET valid_to=%(valid_to)s
                       WHERE security_id=%(security_id)s AND namespace='TICKER' AND identifier=%(old_symbol)s
                         AND scope=%(market_code)s AND (valid_to IS NULL OR valid_to >= %(effective_date)s)""",
                    {"security_id": security_id, "old_symbol": old_symbol.upper(), "market_code": market_code.upper(), "effective_date": effective_date, "valid_to": effective_date - dt.timedelta(days=1)})
    add_identifier(security_id, "TICKER", new_symbol, source=source, scope=market_code, valid_from=effective_date)


def mark_delisted(security_id: str, delisted_on: dt.date) -> None:
    ensure_schema()
    with db._conn() as con:
        con.execute("UPDATE security_listings SET status='delisted', valid_to=%(date)s WHERE security_id=%(security_id)s AND (valid_to IS NULL OR valid_to >= %(date)s)", {"security_id": security_id, "date": delisted_on})


def record_filing(filing: dict, facts: list[dict]) -> str:
    """Append one immutable filing and its point-in-time facts."""
    ensure_schema()
    filing_id = filing.get("filing_id") or str(uuid.uuid5(uuid.NAMESPACE_URL, f"{filing['source']}:{filing['security_id']}:{filing['document_id']}"))
    payload = {**filing, "filing_id": filing_id}
    with db._conn() as con:
        con.execute("""INSERT INTO filing_versions (filing_id, security_id, document_id, form_type, period_end, filed_at, accepted_at, source, source_url, content_hash, supersedes_id)
                       VALUES (%(filing_id)s, %(security_id)s, %(document_id)s, %(form_type)s, %(period_end)s, %(filed_at)s, %(accepted_at)s, %(source)s, %(source_url)s, %(content_hash)s, %(supersedes_id)s)
                       ON CONFLICT (security_id, source, document_id) DO NOTHING""", {**payload, "form_type": payload.get("form_type"), "period_end": payload.get("period_end"), "accepted_at": payload.get("accepted_at"), "source_url": payload.get("source_url"), "content_hash": payload.get("content_hash"), "supersedes_id": payload.get("supersedes_id")})
        for fact in facts:
            con.execute("""INSERT INTO point_in_time_facts (filing_id, security_id, statement_type, fact_name, period_start, period_end, fiscal_year, fiscal_period, value, unit, currency, available_at, confidence)
                           VALUES (%(filing_id)s, %(security_id)s, %(statement_type)s, %(fact_name)s, %(period_start)s, %(period_end)s, %(fiscal_year)s, %(fiscal_period)s, %(value)s, %(unit)s, %(currency)s, %(available_at)s, %(confidence)s)
                           ON CONFLICT (filing_id, statement_type, fact_name, period_end, unit) DO NOTHING""",
                        {**fact, "filing_id": filing_id, "security_id": filing["security_id"], "period_start": fact.get("period_start"), "fiscal_year": fact.get("fiscal_year"), "fiscal_period": fact.get("fiscal_period"), "currency": fact.get("currency"), "available_at": fact.get("available_at") or filing["filed_at"]})
    return filing_id


def get_facts_as_of(security_id: str, as_of: dt.datetime, fact_names: list[str] | None = None) -> list[dict]:
    ensure_schema()
    params = {"security_id": security_id, "as_of": as_of, "fact_names": fact_names}
    condition = "AND fact_name = ANY(%(fact_names)s)" if fact_names else ""
    with db._conn() as con:
        con.row_factory = dict_row
        rows = con.execute(f"""SELECT DISTINCT ON (fact_name, period_end, unit) fact_name, period_start, period_end, fiscal_year, fiscal_period, value, unit, currency, available_at, filing_id::text, confidence
                               FROM point_in_time_facts WHERE security_id=%(security_id)s AND available_at <= %(as_of)s
                               AND system_from <= NOW() AND (system_to IS NULL OR system_to > NOW()) {condition}
                               ORDER BY fact_name, period_end, unit, available_at DESC""", params).fetchall()
    return [dict(row) for row in rows]


def list_restatements(security_id: str) -> list[dict]:
    ensure_schema()
    with db._conn() as con:
        con.row_factory = dict_row
        rows = con.execute("""WITH changed AS (
                                   SELECT fact_name, period_end, unit, COUNT(DISTINCT value) AS versions
                                   FROM point_in_time_facts WHERE security_id=%(security_id)s
                                   GROUP BY fact_name, period_end, unit HAVING COUNT(DISTINCT value) > 1
                               )
                               SELECT c.*, first_value.value AS original_value, last_value.value AS latest_value
                               FROM changed c
                               JOIN LATERAL (SELECT value FROM point_in_time_facts f WHERE f.security_id=%(security_id)s AND f.fact_name=c.fact_name AND f.period_end=c.period_end AND f.unit=c.unit ORDER BY available_at, system_from LIMIT 1) first_value ON TRUE
                               JOIN LATERAL (SELECT value FROM point_in_time_facts f WHERE f.security_id=%(security_id)s AND f.fact_name=c.fact_name AND f.period_end=c.period_end AND f.unit=c.unit ORDER BY available_at DESC, system_from DESC LIMIT 1) last_value ON TRUE
                               ORDER BY c.period_end DESC, c.fact_name""", {"security_id": security_id}).fetchall()
    return [dict(row) for row in rows]


def company_data_history(security_id: str) -> dict[str, list[dict]]:
    """Return sourced identity, filing, and universe timelines for research UI."""
    ensure_schema()
    queries = {
        "identifiers": "SELECT namespace, identifier, scope, valid_from, valid_to, source, confidence FROM security_identifiers WHERE security_id=%(security_id)s ORDER BY namespace, valid_from DESC",
        "filings": "SELECT document_id, form_type, period_end, filed_at, source, source_url FROM filing_versions WHERE security_id=%(security_id)s ORDER BY filed_at DESC LIMIT 100",
        "universes": "SELECT u.code, u.name, m.valid_from, m.valid_to, m.source FROM universe_memberships m JOIN market_universes u USING (universe_id) WHERE m.security_id=%(security_id)s ORDER BY m.valid_from DESC",
    }
    with db._conn() as con:
        con.row_factory = dict_row
        return {name: [dict(row) for row in con.execute(sql, {"security_id": security_id}).fetchall()] for name, sql in queries.items()}


def upsert_corporate_action(action: dict) -> str:
    ensure_schema()
    action_id = action.get("action_id") or str(uuid.uuid5(uuid.NAMESPACE_URL, f"{action['source']}:{action['provider_event_id']}:{action.get('version', 1)}"))
    fields = ("security_id", "action_type", "provider_event_id", "announced_at", "effective_date", "ex_date", "record_date", "payment_date", "ratio", "amount", "currency", "source", "source_url", "version")
    payload = {key: action.get(key) for key in fields} | {"action_id": action_id, "version": action.get("version", 1)}
    with db._conn() as con:
        con.execute("""INSERT INTO corporate_actions (action_id, security_id, action_type, provider_event_id, announced_at, effective_date, ex_date, record_date, payment_date, ratio, amount, currency, source, source_url, version)
                       VALUES (%(action_id)s, %(security_id)s, %(action_type)s, %(provider_event_id)s, %(announced_at)s, %(effective_date)s, %(ex_date)s, %(record_date)s, %(payment_date)s, %(ratio)s, %(amount)s, %(currency)s, %(source)s, %(source_url)s, %(version)s)
                       ON CONFLICT (source, provider_event_id, version) DO NOTHING""", payload)
    return action_id


def list_corporate_actions(security_id: str, as_of: dt.date | None = None) -> list[dict]:
    ensure_schema()
    with db._conn() as con:
        con.row_factory = dict_row
        rows = con.execute("SELECT * FROM corporate_actions WHERE security_id=%(security_id)s AND effective_date <= %(as_of)s ORDER BY effective_date DESC", {"security_id": security_id, "as_of": as_of or dt.date.today()}).fetchall()
    return [dict(row) for row in rows]


def upsert_price(row: dict) -> None:
    ensure_schema()
    with db._conn() as con:
        con.execute("""INSERT INTO daily_prices (security_id, price_date, open, high, low, close, adjusted_close, volume, currency, adjustment_version, source)
                       VALUES (%(security_id)s, %(price_date)s, %(open)s, %(high)s, %(low)s, %(close)s, %(adjusted_close)s, %(volume)s, %(currency)s, %(adjustment_version)s, %(source)s)
                       ON CONFLICT (security_id, price_date, source) DO UPDATE SET open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, adjusted_close=excluded.adjusted_close, volume=excluded.volume, currency=excluded.currency, adjustment_version=excluded.adjustment_version, observed_at=NOW()""", row)


def get_price_history(security_id: str, start: dt.date, end: dt.date, *, as_of: dt.datetime | None = None) -> list[dict]:
    """Return observations known by ``as_of``; never substitute current prices."""
    ensure_schema()
    cutoff = as_of or dt.datetime.now(dt.timezone.utc)
    with db._conn() as con:
        con.row_factory = dict_row
        rows = con.execute("""SELECT price_date AS "Date", close AS "Close", adjusted_close AS "AdjClose", currency, source
                               FROM daily_prices WHERE security_id=%(security_id)s AND price_date BETWEEN %(start)s AND %(end)s
                               AND observed_at <= %(as_of)s ORDER BY price_date""",
                           {"security_id": security_id, "start": start, "end": end, "as_of": cutoff}).fetchall()
    return [dict(row) for row in rows]


def upsert_fx_rate(row: dict) -> None:
    ensure_schema()
    with db._conn() as con:
        con.execute("""INSERT INTO fx_rates (base_currency, quote_currency, rate_date, rate, source)
                       VALUES (%(base_currency)s, %(quote_currency)s, %(rate_date)s, %(rate)s, %(source)s)
                       ON CONFLICT (base_currency, quote_currency, rate_date, source) DO UPDATE SET rate=excluded.rate, observed_at=NOW()""", row)


def get_fx_rate(base: str, quote: str, date: dt.date) -> float | None:
    if base.upper() == quote.upper():
        return 1.0
    ensure_schema()
    with db._conn() as con:
        row = con.execute("""SELECT rate FROM fx_rates WHERE base_currency=%(base)s AND quote_currency=%(quote)s AND rate_date <= %(date)s ORDER BY rate_date DESC, observed_at DESC LIMIT 1""", {"base": base.upper(), "quote": quote.upper(), "date": date}).fetchone()
    return float(row[0]) if row else None


def get_universe_members(code: str, as_of: dt.date) -> list[dict]:
    ensure_schema()
    with db._conn() as con:
        con.row_factory = dict_row
        rows = con.execute("""SELECT m.security_id::text, i.identifier AS symbol, e.legal_name
                               FROM market_universes u JOIN universe_memberships m USING (universe_id)
                               JOIN securities s USING (security_id) JOIN security_entities e USING (entity_id)
                               LEFT JOIN security_identifiers i ON i.security_id=m.security_id AND i.namespace='TICKER'
                                    AND i.valid_from <= %(as_of)s AND (i.valid_to IS NULL OR i.valid_to >= %(as_of)s)
                               WHERE u.code=%(code)s AND m.valid_from <= %(as_of)s AND (m.valid_to IS NULL OR m.valid_to >= %(as_of)s)
                               ORDER BY i.identifier""", {"code": code.upper(), "as_of": as_of}).fetchall()
    return [dict(row) for row in rows]


def replace_universe_history(code: str, name: str, memberships: list[dict], *, source: str, market_code: str = "US") -> int:
    """Idempotently add sourced membership intervals without deleting history."""
    ensure_schema()
    universe_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"factorresearch:universe:{code.upper()}"))
    with db._conn() as con:
        con.execute("""INSERT INTO market_universes (universe_id, code, name, market_code, source)
                       VALUES (%(universe_id)s, %(code)s, %(name)s, %(market_code)s, %(source)s)
                       ON CONFLICT (code) DO UPDATE SET name=excluded.name, market_code=excluded.market_code, source=excluded.source""",
                    {"universe_id": universe_id, "code": code.upper(), "name": name, "market_code": market_code, "source": source})
        for row in memberships:
            con.execute("""INSERT INTO universe_memberships (universe_id, security_id, valid_from, valid_to, source)
                           VALUES (%(universe_id)s, %(security_id)s, %(valid_from)s, %(valid_to)s, %(source)s)
                           ON CONFLICT (universe_id, security_id, valid_from) DO UPDATE SET valid_to=excluded.valid_to, source=excluded.source, observed_at=NOW()""",
                        {"universe_id": universe_id, "source": source, **row})
    return len(memberships)


def checkpoint(dataset: str, item_key: str, *, status: str, rows_written: int = 0, error: str | None = None) -> None:
    ensure_schema()
    with db._conn() as con:
        con.execute("""INSERT INTO track_e_ingestion_checkpoints (dataset, item_key, status, rows_written, error, completed_at)
                       VALUES (%(dataset)s, %(item_key)s, %(status)s, %(rows_written)s, %(error)s,
                               CASE WHEN %(status)s IN ('complete', 'failed') THEN NOW() END)
                       ON CONFLICT (dataset, item_key) DO UPDATE SET status=excluded.status,
                           rows_written=excluded.rows_written, error=excluded.error,
                           started_at=CASE WHEN excluded.status='running' THEN NOW() ELSE track_e_ingestion_checkpoints.started_at END,
                           completed_at=excluded.completed_at""",
                    {"dataset": dataset, "item_key": item_key.upper(), "status": status, "rows_written": rows_written, "error": error})


def checkpoint_complete(dataset: str, item_key: str) -> bool:
    ensure_schema()
    with db._conn() as con:
        row = con.execute("SELECT 1 FROM track_e_ingestion_checkpoints WHERE dataset=%(dataset)s AND item_key=%(item_key)s AND status='complete'", {"dataset": dataset, "item_key": item_key.upper()}).fetchone()
    return bool(row)


def coverage_report() -> dict:
    ensure_schema()
    queries = {
        "securities": "SELECT COUNT(*) FROM securities",
        "identified_securities": "SELECT COUNT(DISTINCT security_id) FROM security_identifiers",
        "filings": "SELECT COUNT(*) FROM filing_versions",
        "facts": "SELECT COUNT(*) FROM point_in_time_facts",
        "actions": "SELECT COUNT(*) FROM corporate_actions",
        "price_rows": "SELECT COUNT(*) FROM daily_prices",
        "fx_rows": "SELECT COUNT(*) FROM fx_rates",
        "universe_memberships": "SELECT COUNT(*) FROM universe_memberships",
        "unresolved_identifiers": "SELECT COUNT(*) FROM securities s WHERE NOT EXISTS (SELECT 1 FROM security_identifiers i WHERE i.security_id=s.security_id AND i.namespace='TICKER')",
    }
    with db._conn() as con:
        return {name: int(con.execute(sql).fetchone()[0]) for name, sql in queries.items()}
