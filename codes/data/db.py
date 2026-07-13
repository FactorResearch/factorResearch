"""
Persistent value metrics store — Postgres only.

Per KNOWN_ISSUES ISSUE_002, market/company data stays in the
`factorresearch_market` database. User/account state such as
subscriptions, usage counters, and user weights may live in a dedicated
`factorresearch_users` database via DATABASE_USERS_URL /
FACTORRESEARCH_USERS_DATABASE_URL. SQLite has been fully removed.

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


_market_initialized = False
_users_initialized = False

_CREATE_MARKET_TABLES = """
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

CREATE TABLE IF NOT EXISTS sec_8k_filings (
    ticker      TEXT NOT NULL,
    accession   TEXT NOT NULL,
    form        TEXT,
    filing_date TEXT,
    document    TEXT,
    source_url  TEXT,
    text        TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (ticker, accession)
);

CREATE INDEX IF NOT EXISTS idx_sec_8k_filings_ticker_date
    ON sec_8k_filings(ticker, filing_date DESC);

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
CREATE TABLE IF NOT EXISTS factor_scores (
    ticker       TEXT NOT NULL,
    factor_name  TEXT NOT NULL,
    score        REAL,
    max_score    REAL,
    computed_at  TEXT NOT NULL,
    PRIMARY KEY (ticker, factor_name)
);
CREATE TABLE IF NOT EXISTS strategy_backtest_cache (
    cache_key   TEXT PRIMARY KEY,
    result_json TEXT NOT NULL,
    computed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS factor_score_snapshots (
    ticker         TEXT NOT NULL,
    factor_name    TEXT NOT NULL,
    snapshot_date  TEXT NOT NULL,   -- YYYY-MM-DD, the rebalance date this reflects
    score          REAL,
    max_score      REAL,
    recorded_at    TEXT NOT NULL,
    PRIMARY KEY (ticker, factor_name, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_factor_snapshots_ticker_date
    ON factor_score_snapshots(ticker, snapshot_date);

CREATE TABLE IF NOT EXISTS composite_score_snapshots (
    ticker            TEXT NOT NULL,
    snapshot_date     DATE NOT NULL,
    algorithm_version TEXT NOT NULL DEFAULT 'enhanced-v1',
    composite_score   REAL NOT NULL,
    verdict           TEXT,
    recorded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ticker, snapshot_date, algorithm_version)
);

CREATE INDEX IF NOT EXISTS idx_composite_snapshots_ticker_date
    ON composite_score_snapshots(ticker, snapshot_date DESC);

CREATE TABLE IF NOT EXISTS canada_issuers (
    symbol     TEXT PRIMARY KEY,
    name       TEXT,
    exchange   TEXT,
    country    TEXT NOT NULL DEFAULT 'Canada',
    currency   TEXT NOT NULL DEFAULT 'CAD',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canada_fiscal_periods (
    symbol        TEXT NOT NULL,
    fiscal_year   INTEGER NOT NULL,
    fiscal_period TEXT NOT NULL,
    period_end    TEXT NOT NULL,
    currency      TEXT NOT NULL,
    PRIMARY KEY (symbol, fiscal_year, fiscal_period)
);

CREATE TABLE IF NOT EXISTS canada_source_documents (
    symbol      TEXT NOT NULL,
    document_id TEXT NOT NULL,
    source      TEXT NOT NULL,
    url         TEXT,
    filing_date TEXT,
    period_end  TEXT,
    form        TEXT,
    confidence  TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    PRIMARY KEY (symbol, document_id)
);

CREATE TABLE IF NOT EXISTS canada_statement_facts (
    symbol               TEXT NOT NULL,
    statement_type       TEXT NOT NULL,
    fact_name            TEXT NOT NULL,
    fiscal_year          INTEGER NOT NULL,
    fiscal_period        TEXT NOT NULL,
    period_end           TEXT NOT NULL,
    currency             TEXT NOT NULL,
    value                DOUBLE PRECISION NOT NULL,
    source_document_id   TEXT NOT NULL,
    source_url           TEXT,
    confidence           TEXT NOT NULL,
    accounting_standard  TEXT,
    extraction_method    TEXT,
    normalization_method TEXT,
    ingested_at          TEXT NOT NULL,
    PRIMARY KEY (symbol, statement_type, fact_name, fiscal_year, fiscal_period)
);

CREATE INDEX IF NOT EXISTS idx_canada_statement_facts_symbol_year
    ON canada_statement_facts(symbol, fiscal_year DESC);

CREATE TABLE IF NOT EXISTS canada_shares_outstanding (
    symbol             TEXT PRIMARY KEY,
    shares_outstanding DOUBLE PRECISION NOT NULL,
    as_of              TEXT NOT NULL,
    source             TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canada_quality_reports (
    symbol     TEXT PRIMARY KEY,
    market     TEXT NOT NULL,
    can_score  BOOLEAN NOT NULL,
    confidence TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canada_quality_issues (
    symbol   TEXT NOT NULL,
    code     TEXT NOT NULL,
    field    TEXT,
    severity TEXT NOT NULL,
    message  TEXT NOT NULL,
    PRIMARY KEY (symbol, code, field)
);

"""
_CREATE_USER_TABLES = """
CREATE TABLE IF NOT EXISTS user_weights (
    user_id      TEXT NOT NULL,
    factor_name  TEXT NOT NULL,
    weight       REAL NOT NULL,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (user_id, factor_name)
);
CREATE TABLE IF NOT EXISTS subscriptions (
    id                     BIGSERIAL PRIMARY KEY,
    user_id                TEXT NOT NULL UNIQUE,
    plan                   TEXT NOT NULL DEFAULT 'free',
    status                 TEXT NOT NULL DEFAULT 'trialing',
    start_date             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_date               TIMESTAMPTZ,
    stripe_customer_id     TEXT,
    stripe_subscription_id TEXT,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_stripe_customer
    ON subscriptions(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_stripe_subscription
    ON subscriptions(stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS user_usage (
    user_id       TEXT NOT NULL,
    period_start  TIMESTAMPTZ NOT NULL,
    period_end    TIMESTAMPTZ NOT NULL,
    feature_name  TEXT NOT NULL,
    usage_count   INTEGER NOT NULL DEFAULT 0,
    feature_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, period_start, feature_name)
);
CREATE TABLE IF NOT EXISTS waitlist_signups (
    email                TEXT PRIMARY KEY,
    source               TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmation_sent_at TIMESTAMPTZ
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

_UPSERT_CANADA_ISSUER = """
INSERT INTO canada_issuers (symbol, name, exchange, country, currency, updated_at)
VALUES (%(symbol)s, %(name)s, %(exchange)s, %(country)s, %(currency)s, %(updated_at)s)
ON CONFLICT (symbol) DO UPDATE SET
    name = excluded.name,
    exchange = excluded.exchange,
    country = excluded.country,
    currency = excluded.currency,
    updated_at = excluded.updated_at
"""
_DELETE_CANADA_PERIODS = "DELETE FROM canada_fiscal_periods WHERE symbol = %(symbol)s"
_INSERT_CANADA_PERIOD = """
INSERT INTO canada_fiscal_periods (symbol, fiscal_year, fiscal_period, period_end, currency)
VALUES (%(symbol)s, %(fiscal_year)s, %(fiscal_period)s, %(period_end)s, %(currency)s)
ON CONFLICT (symbol, fiscal_year, fiscal_period) DO UPDATE SET
    period_end = excluded.period_end,
    currency = excluded.currency
"""
_DELETE_CANADA_DOCUMENTS = "DELETE FROM canada_source_documents WHERE symbol = %(symbol)s"
_INSERT_CANADA_DOCUMENT = """
INSERT INTO canada_source_documents (
    symbol, document_id, source, url, filing_date, period_end, form, confidence, ingested_at
)
VALUES (
    %(symbol)s, %(document_id)s, %(source)s, %(url)s, %(filing_date)s,
    %(period_end)s, %(form)s, %(confidence)s, %(ingested_at)s
)
ON CONFLICT (symbol, document_id) DO UPDATE SET
    source = excluded.source,
    url = excluded.url,
    filing_date = excluded.filing_date,
    period_end = excluded.period_end,
    form = excluded.form,
    confidence = excluded.confidence,
    ingested_at = excluded.ingested_at
"""
_DELETE_CANADA_FACTS = "DELETE FROM canada_statement_facts WHERE symbol = %(symbol)s"
_INSERT_CANADA_FACT = """
INSERT INTO canada_statement_facts (
    symbol, statement_type, fact_name, fiscal_year, fiscal_period, period_end,
    currency, value, source_document_id, source_url, confidence,
    accounting_standard, extraction_method, normalization_method, ingested_at
)
VALUES (
    %(symbol)s, %(statement_type)s, %(fact_name)s, %(fiscal_year)s, %(fiscal_period)s,
    %(period_end)s, %(currency)s, %(value)s, %(source_document_id)s, %(source_url)s,
    %(confidence)s, %(accounting_standard)s, %(extraction_method)s,
    %(normalization_method)s, %(ingested_at)s
)
ON CONFLICT (symbol, statement_type, fact_name, fiscal_year, fiscal_period) DO UPDATE SET
    period_end = excluded.period_end,
    currency = excluded.currency,
    value = excluded.value,
    source_document_id = excluded.source_document_id,
    source_url = excluded.source_url,
    confidence = excluded.confidence,
    accounting_standard = excluded.accounting_standard,
    extraction_method = excluded.extraction_method,
    normalization_method = excluded.normalization_method,
    ingested_at = excluded.ingested_at
"""
_UPSERT_CANADA_SHARES = """
INSERT INTO canada_shares_outstanding (symbol, shares_outstanding, as_of, source, updated_at)
VALUES (%(symbol)s, %(shares_outstanding)s, %(as_of)s, %(source)s, %(updated_at)s)
ON CONFLICT (symbol) DO UPDATE SET
    shares_outstanding = excluded.shares_outstanding,
    as_of = excluded.as_of,
    source = excluded.source,
    updated_at = excluded.updated_at
"""
_UPSERT_CANADA_QUALITY = """
INSERT INTO canada_quality_reports (symbol, market, can_score, confidence, updated_at)
VALUES (%(symbol)s, %(market)s, %(can_score)s, %(confidence)s, %(updated_at)s)
ON CONFLICT (symbol) DO UPDATE SET
    market = excluded.market,
    can_score = excluded.can_score,
    confidence = excluded.confidence,
    updated_at = excluded.updated_at
"""
_DELETE_CANADA_QUALITY_ISSUES = "DELETE FROM canada_quality_issues WHERE symbol = %(symbol)s"
_INSERT_CANADA_QUALITY_ISSUE = """
INSERT INTO canada_quality_issues (symbol, code, field, severity, message)
VALUES (%(symbol)s, %(code)s, %(field)s, %(severity)s, %(message)s)
ON CONFLICT (symbol, code, field) DO UPDATE SET
    severity = excluded.severity,
    message = excluded.message
"""
_SELECT_CANADA_ISSUER = "SELECT * FROM canada_issuers WHERE symbol = %(symbol)s"
_SELECT_CANADA_PERIODS = """
SELECT fiscal_year, fiscal_period, period_end, currency
FROM canada_fiscal_periods
WHERE symbol = %(symbol)s
ORDER BY fiscal_year DESC, fiscal_period
"""
_SELECT_CANADA_FACTS = """
SELECT *
FROM canada_statement_facts
WHERE symbol = %(symbol)s AND statement_type = %(statement_type)s
ORDER BY fiscal_year DESC, fact_name
"""
_SELECT_CANADA_DOCUMENTS = """
SELECT document_id, source, url, filing_date, period_end, form, confidence
FROM canada_source_documents
WHERE symbol = %(symbol)s
ORDER BY filing_date DESC NULLS LAST, period_end DESC NULLS LAST, document_id
"""
_SELECT_CANADA_SHARES = """
SELECT shares_outstanding, as_of, source
FROM canada_shares_outstanding
WHERE symbol = %(symbol)s
"""
_SELECT_CANADA_PROVENANCE = """
SELECT DISTINCT ON (fact_name)
    fact_name, source_document_id, source_url, confidence, accounting_standard,
    extraction_method, normalization_method
FROM canada_statement_facts
WHERE symbol = %(symbol)s
ORDER BY fact_name, fiscal_year DESC
"""
_SELECT_CANADA_QUALITY = "SELECT * FROM canada_quality_reports WHERE symbol = %(symbol)s"
_SELECT_CANADA_QUALITY_ISSUES = """
SELECT code, field, severity, message
FROM canada_quality_issues
WHERE symbol = %(symbol)s
ORDER BY severity, code
"""

_UPSERT_SEC_8K = """
INSERT INTO sec_8k_filings (
    ticker, accession, form, filing_date, document, source_url, text, fetched_at
)
VALUES (
    %(ticker)s, %(accession)s, %(form)s, %(filing_date)s, %(document)s,
    %(source_url)s, %(text)s, %(fetched_at)s
)
ON CONFLICT (ticker, accession) DO UPDATE SET
    form = excluded.form,
    filing_date = excluded.filing_date,
    document = excluded.document,
    source_url = excluded.source_url,
    text = excluded.text,
    fetched_at = excluded.fetched_at
"""

_SELECT_SEC_8K = """
SELECT ticker, accession, form, filing_date, document, source_url, text, fetched_at
FROM sec_8k_filings
WHERE ticker = %(ticker)s
ORDER BY filing_date DESC NULLS LAST, fetched_at DESC, accession DESC
LIMIT %(limit)s
"""

_SELECT_SEC_8K_LATEST = """
SELECT accession
FROM sec_8k_filings
WHERE ticker = %(ticker)s
ORDER BY filing_date DESC NULLS LAST, fetched_at DESC, accession DESC
LIMIT 1
"""

_SELECT_SEC_8K_ACCESSIONS = """
SELECT accession
FROM sec_8k_filings
WHERE ticker = %(ticker)s AND accession = ANY(%(accessions)s)
"""


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


def upsert_sec_8k_filings(ticker: str, filings: list[dict]) -> None:
    """Persist fetched SEC 8-K primary-document text by accession."""
    if not filings:
        return
    _ensure_init()
    t = ticker.upper()
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as con:
        for filing in filings:
            accession = filing.get("accession")
            text = filing.get("text")
            if not accession or not text:
                continue
            con.execute(_UPSERT_SEC_8K, {
                "ticker": t,
                "accession": accession,
                "form": filing.get("form"),
                "filing_date": filing.get("filing_date"),
                "document": filing.get("document"),
                "source_url": filing.get("source_url"),
                "text": text,
                "fetched_at": now,
            })


def get_sec_8k_filings(ticker: str, limit: int = 5) -> list[dict]:
    """Return cached SEC 8-K filings newest-first."""
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        rows = con.execute(
            _SELECT_SEC_8K,
            {"ticker": ticker.upper(), "limit": max(1, min(int(limit), 10))},
        ).fetchall()
    return [dict(row) for row in rows]


def get_latest_sec_8k_accession(ticker: str) -> str | None:
    """Return newest cached SEC 8-K accession for ticker, if present."""
    _ensure_init()
    with _conn() as con:
        row = con.execute(
            _SELECT_SEC_8K_LATEST,
            {"ticker": ticker.upper()},
        ).fetchone()
    return row[0] if row else None


def list_existing_sec_8k_accessions(ticker: str, accessions: list[str]) -> set[str]:
    """Return cached accessions from a candidate accession list."""
    if not accessions:
        return set()
    _ensure_init()
    with _conn() as con:
        rows = con.execute(
            _SELECT_SEC_8K_ACCESSIONS,
            {"ticker": ticker.upper(), "accessions": accessions},
        ).fetchall()
    return {row[0] for row in rows}

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


def upsert_canada_canonical_facts(symbol: str, financials, shares, quality_report) -> None:
    """Persist normalized Canada facts in relational market-data tables."""
    _ensure_init()
    t = symbol.upper()
    now = datetime.datetime.utcnow().isoformat()
    company = financials.company
    provenance_by_fact = {item.fact_name: item for item in financials.provenance}

    with _conn() as con:
        con.execute(_UPSERT_CANADA_ISSUER, {
            "symbol": t,
            "name": company.name,
            "exchange": company.exchange,
            "country": company.country or "Canada",
            "currency": company.currency or "CAD",
            "updated_at": now,
        })

        con.execute(_DELETE_CANADA_PERIODS, {"symbol": t})
        for period in financials.periods:
            con.execute(_INSERT_CANADA_PERIOD, {
                "symbol": t,
                "fiscal_year": period.fiscal_year,
                "fiscal_period": period.fiscal_period,
                "period_end": period.period_end,
                "currency": period.currency or company.currency or "CAD",
            })

        con.execute(_DELETE_CANADA_DOCUMENTS, {"symbol": t})
        for document in financials.source_documents:
            con.execute(_INSERT_CANADA_DOCUMENT, {
                "symbol": t,
                "document_id": document.document_id,
                "source": document.source,
                "url": document.url,
                "filing_date": document.filing_date,
                "period_end": document.period_end,
                "form": document.form,
                "confidence": document.confidence,
                "ingested_at": now,
            })

        con.execute(_DELETE_CANADA_FACTS, {"symbol": t})
        for statement_type, rows in (
            ("income", financials.income_statement),
            ("balance", financials.balance_sheet),
            ("cash_flow", financials.cash_flow),
        ):
            for fact in _canada_fact_rows(t, statement_type, rows, financials, provenance_by_fact, now):
                con.execute(_INSERT_CANADA_FACT, fact)

        if shares and shares.shares_outstanding and shares.as_of and shares.source:
            con.execute(_UPSERT_CANADA_SHARES, {
                "symbol": t,
                "shares_outstanding": shares.shares_outstanding,
                "as_of": shares.as_of,
                "source": shares.source,
                "updated_at": now,
            })

        con.execute(_UPSERT_CANADA_QUALITY, {
            "symbol": t,
            "market": quality_report.market,
            "can_score": quality_report.can_score,
            "confidence": quality_report.confidence,
            "updated_at": now,
        })
        con.execute(_DELETE_CANADA_QUALITY_ISSUES, {"symbol": t})
        for issue in quality_report.issues:
            con.execute(_INSERT_CANADA_QUALITY_ISSUE, {
                "symbol": t,
                "code": issue.code,
                "field": issue.field or "",
                "severity": issue.severity,
                "message": issue.message,
            })


def get_canada_company_profile(symbol: str) -> dict | None:
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        row = con.execute(_SELECT_CANADA_ISSUER, {"symbol": symbol.upper()}).fetchone()
    if not row:
        return None
    return {
        "issuer_name": row["name"],
        "exchange": row["exchange"],
        "country": row["country"],
        "currency": row["currency"],
    }


def get_canada_financial_periods(symbol: str) -> list[dict]:
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        rows = con.execute(_SELECT_CANADA_PERIODS, {"symbol": symbol.upper()}).fetchall()
    return [dict(row) for row in rows]


def get_canada_statement_facts(symbol: str, statement_type: str) -> list[dict]:
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        rows = con.execute(
            _SELECT_CANADA_FACTS,
            {"symbol": symbol.upper(), "statement_type": statement_type},
        ).fetchall()
    results: dict[tuple[int, str], dict] = {}
    for row in rows:
        key = (row["fiscal_year"], row["fiscal_period"])
        item = results.setdefault(key, {
            "fiscal_year": row["fiscal_year"],
            "fiscal_period": row["fiscal_period"],
            "period_end": row["period_end"],
            "currency": row["currency"],
        })
        item[row["fact_name"]] = row["value"]
    return list(results.values())


def get_canada_filings(symbol: str) -> list[dict]:
    return get_canada_source_documents(symbol)


def get_canada_source_documents(symbol: str) -> list[dict]:
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        rows = con.execute(_SELECT_CANADA_DOCUMENTS, {"symbol": symbol.upper()}).fetchall()
    return [dict(row) for row in rows]


def get_canada_shares_outstanding(symbol: str) -> dict | None:
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        row = con.execute(_SELECT_CANADA_SHARES, {"symbol": symbol.upper()}).fetchone()
    return dict(row) if row else None


def get_canada_statement_provenance(symbol: str) -> list[dict]:
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        rows = con.execute(_SELECT_CANADA_PROVENANCE, {"symbol": symbol.upper()}).fetchall()
    return [dict(row) for row in rows]


def get_canada_quality_report(symbol: str) -> dict | None:
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        report = con.execute(_SELECT_CANADA_QUALITY, {"symbol": symbol.upper()}).fetchone()
        issues = con.execute(_SELECT_CANADA_QUALITY_ISSUES, {"symbol": symbol.upper()}).fetchall()
    if not report:
        return None
    result = dict(report)
    result["issues"] = [dict(issue) for issue in issues]
    return result


def _canada_fact_rows(
    symbol: str,
    statement_type: str,
    rows,
    financials,
    provenance_by_fact: dict,
    ingested_at: str,
) -> list[dict]:
    facts = []
    for row in rows:
        period = _canada_period_for_row(financials.periods, row)
        if period is None:
            continue
        for fact_name, value in row.items():
            if fact_name in {"fiscal_year", "year", "fiscal_period", "period", "period_end", "end", "end_date", "currency"}:
                continue
            numeric = _float_or_none(value)
            provenance = provenance_by_fact.get(fact_name)
            if numeric is None or provenance is None or not provenance.source_document_id:
                continue
            facts.append({
                "symbol": symbol,
                "statement_type": statement_type,
                "fact_name": fact_name,
                "fiscal_year": period.fiscal_year,
                "fiscal_period": period.fiscal_period,
                "period_end": period.period_end,
                "currency": row.get("currency") or period.currency or financials.company.currency or "CAD",
                "value": numeric,
                "source_document_id": provenance.source_document_id,
                "source_url": provenance.source_url,
                "confidence": provenance.confidence,
                "accounting_standard": provenance.accounting_standard,
                "extraction_method": provenance.extraction_method,
                "normalization_method": provenance.normalization_method,
                "ingested_at": ingested_at,
            })
    return facts


def _canada_period_for_row(periods, row: dict):
    year = row.get("fiscal_year") or row.get("year")
    end = row.get("period_end") or row.get("end") or row.get("end_date")
    for period in periods:
        if period.period_end == end or period.fiscal_year == year:
            return period
    return periods[0] if periods else None


def _float_or_none(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_UPSERT_FACTOR_SCORE = """
INSERT INTO factor_scores (ticker, factor_name, score, max_score, computed_at)
VALUES (%(ticker)s, %(factor_name)s, %(score)s, %(max_score)s, %(computed_at)s)
ON CONFLICT (ticker, factor_name) DO UPDATE SET
    score = excluded.score, max_score = excluded.max_score, computed_at = excluded.computed_at
"""
_SELECT_FACTOR_SCORES = "SELECT factor_name, score, max_score, computed_at FROM factor_scores WHERE ticker = %(ticker)s"


def upsert_factor_scores(ticker: str, scores: dict[str, tuple[float | None, float | None]]) -> None:
    """
    Persist atomic factor scores for one company (ISSUE_012 Layer 1).
    `scores` maps factor_name -> (score, max_score). Shared across all
    users — this is company-level data, never duplicated per user.
    """
    _ensure_init()
    t = ticker.upper()
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as con:
        for factor_name, (score, max_score) in scores.items():
            con.execute(_UPSERT_FACTOR_SCORE, {
                "ticker": t, "factor_name": factor_name,
                "score": score, "max_score": max_score, "computed_at": now,
            })

_UPSERT_USER_WEIGHT = """
INSERT INTO user_weights (user_id, factor_name, weight, updated_at)
VALUES (%(user_id)s, %(factor_name)s, %(weight)s, %(updated_at)s)
ON CONFLICT (user_id, factor_name) DO UPDATE SET
    weight = excluded.weight, updated_at = excluded.updated_at
"""
_SELECT_USER_WEIGHTS = "SELECT factor_name, weight FROM user_weights WHERE user_id = %(user_id)s"
_DELETE_USER_WEIGHTS = "DELETE FROM user_weights WHERE user_id = %(user_id)s"


def set_user_weights(user_id: str, weights: dict[str, float]) -> None:
    """Persist a user's factor weight config. Only the weights — never
    company data — are duplicated per user (ISSUE_012 Layer 3)."""
    _ensure_user_init()
    now = datetime.datetime.utcnow().isoformat()
    with _users_conn() as con:
        con.execute(_DELETE_USER_WEIGHTS, {"user_id": user_id})
        for factor_name, weight in weights.items():
            con.execute(_UPSERT_USER_WEIGHT, {
                "user_id": user_id, "factor_name": factor_name,
                "weight": weight, "updated_at": now,
            })


def get_user_weights(user_id: str) -> dict[str, float]:
    _ensure_user_init()
    with _users_conn() as con:
        con.row_factory = dict_row
        rows = con.execute(_SELECT_USER_WEIGHTS, {"user_id": user_id}).fetchall()
    return {r["factor_name"]: r["weight"] for r in rows}
def get_factor_scores(ticker: str) -> dict[str, dict]:
    """Return {factor_name: {score, max_score, computed_at}} for a ticker."""
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        rows = con.execute(_SELECT_FACTOR_SCORES, {"ticker": ticker.upper()}).fetchall()
    return {r["factor_name"]: {"score": r["score"], "max_score": r["max_score"],
                                "computed_at": r["computed_at"]} for r in rows}

_UPSERT_STRATEGY_CACHE = """
INSERT INTO strategy_backtest_cache (cache_key, result_json, computed_at)
VALUES (%(cache_key)s, %(result_json)s, %(computed_at)s)
ON CONFLICT (cache_key) DO UPDATE SET
    result_json = excluded.result_json, computed_at = excluded.computed_at
"""
_SELECT_STRATEGY_CACHE = "SELECT result_json, computed_at FROM strategy_backtest_cache WHERE cache_key = %(cache_key)s"
_DELETE_STRATEGY_CACHE_PREFIX = "DELETE FROM strategy_backtest_cache WHERE cache_key LIKE %(prefix)s"

_SELECT_SUBSCRIPTION = "SELECT * FROM subscriptions WHERE user_id = %(user_id)s"
_SELECT_SUBSCRIPTION_BY_CUSTOMER = "SELECT * FROM subscriptions WHERE stripe_customer_id = %(stripe_customer_id)s"
_SELECT_SUBSCRIPTION_BY_STRIPE_ID = "SELECT * FROM subscriptions WHERE stripe_subscription_id = %(stripe_subscription_id)s"
_UPSERT_SUBSCRIPTION = """
INSERT INTO subscriptions (
    user_id, plan, status, start_date, end_date,
    stripe_customer_id, stripe_subscription_id, updated_at
)
VALUES (
    %(user_id)s, %(plan)s, %(status)s,
    COALESCE(%(start_date)s, NOW()), %(end_date)s,
    %(stripe_customer_id)s, %(stripe_subscription_id)s, NOW()
)
ON CONFLICT (user_id) DO UPDATE SET
    plan = excluded.plan,
    status = excluded.status,
    start_date = COALESCE(excluded.start_date, subscriptions.start_date),
    end_date = excluded.end_date,
    stripe_customer_id = COALESCE(excluded.stripe_customer_id, subscriptions.stripe_customer_id),
    stripe_subscription_id = COALESCE(excluded.stripe_subscription_id, subscriptions.stripe_subscription_id),
    updated_at = NOW()
"""
_SELECT_USAGE = """
SELECT usage_count, feature_usage, period_start, period_end
FROM user_usage
WHERE user_id = %(user_id)s
  AND feature_name = %(feature_name)s
  AND NOW() >= period_start
  AND NOW() < period_end
ORDER BY period_start DESC
LIMIT 1
"""
_SELECT_TOTAL_USAGE = """
SELECT COALESCE(SUM(usage_count), 0) AS usage_count
FROM user_usage
WHERE user_id = %(user_id)s
  AND feature_name = %(feature_name)s
"""
_INCREMENT_USAGE = """
INSERT INTO user_usage (
    user_id, period_start, period_end, feature_name, usage_count, feature_usage, updated_at
)
VALUES (
    %(user_id)s, %(period_start)s, %(period_end)s, %(feature_name)s, 1,
    jsonb_build_object(%(usage_key)s::text, 1), NOW()
)
ON CONFLICT (user_id, period_start, feature_name) DO UPDATE SET
    usage_count = user_usage.usage_count + 1,
    feature_usage = jsonb_set(
        user_usage.feature_usage,
        ARRAY[%(usage_key)s::text],
        to_jsonb(COALESCE((user_usage.feature_usage ->> %(usage_key)s::text)::int, 0) + 1),
        true
    ),
    updated_at = NOW()
RETURNING usage_count, feature_usage, period_start, period_end
"""
_UPSERT_WAITLIST_SIGNUP = """
INSERT INTO waitlist_signups (email, source)
VALUES (%(email)s, %(source)s)
ON CONFLICT (email) DO UPDATE SET source = excluded.source
WHERE waitlist_signups.confirmation_sent_at IS NULL
RETURNING email
"""
_MARK_WAITLIST_CONFIRMED = """
UPDATE waitlist_signups
SET confirmation_sent_at = NOW()
WHERE email = %(email)s
"""


def get_strategy_backtest(cache_key: str) -> dict | None:
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        row = con.execute(_SELECT_STRATEGY_CACHE, {"cache_key": cache_key}).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["result_json"])
    except (TypeError, ValueError):
        return None


def set_strategy_backtest(cache_key: str, result: dict) -> None:
    _ensure_init()
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as con:
        con.execute(_UPSERT_STRATEGY_CACHE, {
            "cache_key": cache_key,
            "result_json": json.dumps(result, default=str),
            "computed_at": now,
        })


def invalidate_strategy_cache(data_version_prefix: str) -> None:
    """Bulk-invalidate all cached strategies for a stale data_version."""
    _ensure_init()
    with _conn() as con:
        con.execute(_DELETE_STRATEGY_CACHE_PREFIX, {"prefix": f"{data_version_prefix}%"})


def get_subscription(user_id: str) -> dict | None:
    _ensure_user_init()
    with _users_conn() as con:
        con.row_factory = dict_row
        row = con.execute(_SELECT_SUBSCRIPTION, {"user_id": user_id}).fetchone()
    return dict(row) if row else None


def get_subscription_by_customer(stripe_customer_id: str) -> dict | None:
    _ensure_user_init()
    with _users_conn() as con:
        con.row_factory = dict_row
        row = con.execute(
            _SELECT_SUBSCRIPTION_BY_CUSTOMER,
            {"stripe_customer_id": stripe_customer_id},
        ).fetchone()
    return dict(row) if row else None


def get_subscription_by_stripe_id(stripe_subscription_id: str) -> dict | None:
    _ensure_user_init()
    with _users_conn() as con:
        con.row_factory = dict_row
        row = con.execute(
            _SELECT_SUBSCRIPTION_BY_STRIPE_ID,
            {"stripe_subscription_id": stripe_subscription_id},
        ).fetchone()
    return dict(row) if row else None


def upsert_subscription(
    user_id: str,
    *,
    plan: str = "free",
    status: str = "trialing",
    start_date=None,
    end_date=None,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
) -> dict:
    _ensure_user_init()
    with _users_conn() as con:
        con.row_factory = dict_row
        con.execute(_UPSERT_SUBSCRIPTION, {
            "user_id": user_id,
            "plan": plan,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id,
        })
        row = con.execute(_SELECT_SUBSCRIPTION, {"user_id": user_id}).fetchone()
    return dict(row)


def get_usage(user_id: str, feature_name: str) -> dict:
    _ensure_user_init()
    with _users_conn() as con:
        con.row_factory = dict_row
        row = con.execute(_SELECT_USAGE, {
            "user_id": user_id,
            "feature_name": feature_name,
        }).fetchone()
    if not row:
        return {"usage_count": 0, "feature_usage": {}}
    result = dict(row)
    result["feature_usage"] = result.get("feature_usage") or {}
    return result


def get_total_usage(user_id: str, feature_name: str) -> int:
    _ensure_user_init()
    with _users_conn() as con:
        row = con.execute(_SELECT_TOTAL_USAGE, {
            "user_id": user_id,
            "feature_name": feature_name,
        }).fetchone()
    return int(row[0] or 0) if row else 0


def increment_usage(user_id: str, feature_name: str, usage_key: str | None = None) -> dict:
    _ensure_user_init()
    now = datetime.datetime.utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        period_end = period_start.replace(year=period_start.year + 1, month=1)
    else:
        period_end = period_start.replace(month=period_start.month + 1)
    with _users_conn() as con:
        con.row_factory = dict_row
        row = con.execute(_INCREMENT_USAGE, {
            "user_id": user_id,
            "period_start": period_start,
            "period_end": period_end,
            "feature_name": feature_name,
            "usage_key": usage_key or feature_name,
        }).fetchone()
    result = dict(row)
    result["feature_usage"] = result.get("feature_usage") or {}
    return result


def consume_limited_usage(
    user_id: str,
    feature_name: str,
    limit: int,
    usage_key: str | None = None,
) -> dict | None:
    """Atomically record usage only while the lifetime feature limit remains."""
    _ensure_user_init()
    now = datetime.datetime.utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        period_end = period_start.replace(year=period_start.year + 1, month=1)
    else:
        period_end = period_start.replace(month=period_start.month + 1)
    with _users_conn() as con:
        con.row_factory = dict_row
        con.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%(usage_lock)s))",
            {"usage_lock": f"{user_id}:{feature_name}"},
        )
        used = con.execute(_SELECT_TOTAL_USAGE, {
            "user_id": user_id,
            "feature_name": feature_name,
        }).fetchone()[0]
        if int(used or 0) >= limit:
            return None
        row = con.execute(_INCREMENT_USAGE, {
            "user_id": user_id,
            "period_start": period_start,
            "period_end": period_end,
            "feature_name": feature_name,
            "usage_key": usage_key or feature_name,
        }).fetchone()
    result = dict(row)
    result["feature_usage"] = result.get("feature_usage") or {}
    return result


def create_waitlist_signup(email: str, source: str) -> bool:
    """Store a waitlist email and return whether it still needs confirmation."""
    _ensure_user_init()
    with _users_conn() as con:
        row = con.execute(_UPSERT_WAITLIST_SIGNUP, {"email": email, "source": source}).fetchone()
    return bool(row)


def mark_waitlist_confirmation_sent(email: str) -> None:
    _ensure_user_init()
    with _users_conn() as con:
        con.execute(_MARK_WAITLIST_CONFIRMED, {"email": email})

_UPSERT_FACTOR_SNAPSHOT = """
INSERT INTO factor_score_snapshots (ticker, factor_name, snapshot_date, score, max_score, recorded_at)
VALUES (%(ticker)s, %(factor_name)s, %(snapshot_date)s, %(score)s, %(max_score)s, %(recorded_at)s)
ON CONFLICT (ticker, factor_name, snapshot_date) DO UPDATE SET
    score = excluded.score, max_score = excluded.max_score, recorded_at = excluded.recorded_at
"""
_SELECT_SNAPSHOTS_ASOF = """
SELECT factor_name, score, max_score, snapshot_date
FROM factor_score_snapshots
WHERE ticker = %(ticker)s AND factor_name = %(factor_name)s AND snapshot_date <= %(as_of)s
ORDER BY snapshot_date DESC
LIMIT 1
"""
_SELECT_SNAPSHOT_DATES = "SELECT DISTINCT snapshot_date FROM factor_score_snapshots WHERE ticker = %(ticker)s ORDER BY snapshot_date"
_UPSERT_COMPOSITE_SNAPSHOT = """
INSERT INTO composite_score_snapshots (
    ticker, snapshot_date, algorithm_version, composite_score, verdict, recorded_at
)
VALUES (%(ticker)s, %(snapshot_date)s, %(algorithm_version)s, %(composite_score)s, %(verdict)s, NOW())
ON CONFLICT (ticker, snapshot_date, algorithm_version) DO UPDATE SET
    composite_score = excluded.composite_score,
    verdict = excluded.verdict,
    recorded_at = NOW()
"""
_SELECT_COMPOSITE_SNAPSHOTS = """
SELECT snapshot_date, composite_score, verdict
FROM composite_score_snapshots
WHERE ticker = %(ticker)s
ORDER BY snapshot_date DESC
LIMIT %(limit)s
"""


def record_factor_snapshot(ticker: str, snapshot_date: str,
                           scores: dict[str, tuple[float | None, float | None]]) -> None:
    """
    Append-only dated snapshot of factor scores (ISSUE_012 Layer 5).
    Unlike factor_scores (Layer 1, latest-only), this never overwrites
    prior dates — each (ticker, factor_name, snapshot_date) is immutable
    once written for that date.
    """
    _ensure_init()
    t = ticker.upper()
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as con:
        for factor_name, (score, max_score) in scores.items():
            con.execute(_UPSERT_FACTOR_SNAPSHOT, {
                "ticker": t, "factor_name": factor_name, "snapshot_date": snapshot_date,
                "score": score, "max_score": max_score, "recorded_at": now,
            })


def get_factor_score_asof(ticker: str, factor_name: str, as_of: str) -> dict | None:
    """Most recent snapshot on or before `as_of` (YYYY-MM-DD), or None."""
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        row = con.execute(_SELECT_SNAPSHOTS_ASOF, {
            "ticker": ticker.upper(), "factor_name": factor_name, "as_of": as_of,
        }).fetchone()
    return dict(row) if row else None


def list_snapshot_dates(ticker: str) -> list[str]:
    _ensure_init()
    with _conn() as con:
        rows = con.execute(_SELECT_SNAPSHOT_DATES, {"ticker": ticker.upper()}).fetchall()
    return [r[0] for r in rows]


def record_composite_score_snapshot(
    ticker: str,
    composite_score: float,
    verdict: str | None,
    snapshot_date: datetime.date | None = None,
    algorithm_version: str = "enhanced-v1",
) -> None:
    """Store one current composite observation per ticker and day."""
    _ensure_init()
    with _conn() as con:
        con.execute(_UPSERT_COMPOSITE_SNAPSHOT, {
            "ticker": ticker.upper(),
            "snapshot_date": snapshot_date or datetime.date.today(),
            "algorithm_version": algorithm_version,
            "composite_score": float(composite_score),
            "verdict": verdict,
        })


def list_composite_score_history(ticker: str, limit: int = 90) -> list[dict]:
    """Return oldest-first daily composite observations for charting."""
    _ensure_init()
    with _conn() as con:
        con.row_factory = dict_row
        rows = con.execute(_SELECT_COMPOSITE_SNAPSHOTS, {
            "ticker": ticker.upper(), "limit": max(1, min(int(limit), 365)),
        }).fetchall()
    return [dict(row) for row in reversed(rows)]

def _db_url() -> str:
    url = os.environ.get("DATABASE_MARKET_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_MARKET_URL is not set. SQLite has been removed — "
            "this module requires Postgres (factorresearch_market db). "
            "Set DATABASE_MARKET_URL to a valid Postgres connection string."
        )
    return url


def _users_db_url() -> str:
    return (
        os.environ.get("DATABASE_USERS_URL")
        or os.environ.get("FACTORRESEARCH_USERS_DATABASE_URL")
        or _db_url()
    )


def _pg_conn():
    import psycopg
    return psycopg.connect(_db_url())


def _users_pg_conn():
    import psycopg
    return psycopg.connect(_users_db_url())


@contextmanager
def _conn():
    """Yield a pooled Postgres connection (returned to the pool on exit)."""
    with _pg_conn() as con:
        yield con


@contextmanager
def _users_conn():
    """Yield a Postgres connection for user/account state."""
    with _users_pg_conn() as con:
        yield con


def init_db() -> None:
    with _conn() as con:
        con.execute(_CREATE_MARKET_TABLES)


def init_user_db() -> None:
    with _users_conn() as con:
        con.execute(_CREATE_USER_TABLES)


def _ensure_init() -> None:
    global _market_initialized
    if not _market_initialized:
        init_db()
        _market_initialized = True


def _ensure_user_init() -> None:
    global _users_initialized
    if not _users_initialized:
        init_user_db()
        _users_initialized = True


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
