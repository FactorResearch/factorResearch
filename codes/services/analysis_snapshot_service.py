from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

from codes.core.db_pool import ConnectionPool
from codes.models.analysis_snapshot import (
    PUBLIC_ANALYSIS_TYPES,
    AnalysisSnapshot,
    AnalysisType,
    CustomAnalysisSnapshot,
    company_slug,
)

SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS analysis_snapshots (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    company_name TEXT NOT NULL,
    analysis_date DATE NOT NULL,
    algorithm_version TEXT NOT NULL,
    valuation_score DOUBLE PRECISION,
    quality_score DOUBLE PRECISION,
    growth_score DOUBLE PRECISION,
    momentum_score DOUBLE PRECISION,
    risk_score DOUBLE PRECISION,
    final_rating TEXT NOT NULL,
    intrinsic_value DOUBLE PRECISION,
    market_price DOUBLE PRECISION,
    market_fear_score DOUBLE PRECISION,
    sector TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (ticker, analysis_date, algorithm_version)
);

CREATE TABLE IF NOT EXISTS analysis_versions (
    algorithm_version TEXT PRIMARY KEY,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE analysis_snapshots
ADD COLUMN IF NOT EXISTS sector TEXT;

ALTER TABLE analysis_snapshots
ADD COLUMN IF NOT EXISTS official_metrics JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE analysis_snapshots
DROP CONSTRAINT IF EXISTS analysis_snapshots_ticker_analysis_date_algorithm_version_key;

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_ticker_date
ON analysis_snapshots(ticker, analysis_date DESC, created_at DESC);

UPDATE analysis_snapshots
SET final_rating = CASE
    WHEN valuation_score >= 75 THEN 'HIGH CONVICTION'
    WHEN valuation_score >= 60 THEN 'FAVORABLE'
    WHEN valuation_score >= 45 THEN 'BALANCED'
    WHEN valuation_score >= 30 THEN 'CAUTION'
    ELSE 'UNFAVORABLE'
END
WHERE final_rating IN ('STRONG BUY', 'BUY', 'WATCH', 'HOLD', 'AVOID');

CREATE TABLE IF NOT EXISTS custom_analysis_snapshots (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    company_name TEXT NOT NULL,
    formula_name TEXT NOT NULL,
    formula_version TEXT NOT NULL,
    composite_score DOUBLE PRECISION,
    factors JSONB NOT NULL DEFAULT '{}'::jsonb,
    backtest_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    default_comparison JSONB NOT NULL DEFAULT '{}'::jsonb,
    benchmark_comparison JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT NOT NULL DEFAULT '',
    analysis_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_custom_analysis_owner_ticker_date
ON custom_analysis_snapshots(user_id, ticker, analysis_date DESC, created_at DESC);
"""
_pools: dict[str, ConnectionPool] = {}
_pool_lock = threading.Lock()


def _database_url() -> str | None:
    return (
        os.environ.get("DATABASE_ANALYTICS_URL")
        or os.environ.get("ANALYTICS_DATABASE_URL")
        or os.environ.get("FACTORRESEARCH_ANALYTICS_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("DATABASE_MARKET_URL")
    )


def _database_urls() -> list[str]:
    urls = [
        os.environ.get("DATABASE_ANALYTICS_URL"),
        os.environ.get("ANALYTICS_DATABASE_URL"),
        os.environ.get("FACTORRESEARCH_ANALYTICS_DATABASE_URL"),
        os.environ.get("DATABASE_URL"),
        os.environ.get("DATABASE_MARKET_URL"),
    ]
    return list(dict.fromkeys(url for url in urls if url))


@contextmanager
def _connect() -> Iterator:
    urls = _database_urls()
    if not urls:
        raise RuntimeError("An analytics or market database URL is required for analysis snapshots.")

    pool = None
    last_error = None
    for dsn in urls:
        try:
            with _pool_lock:
                pool = _pools.get(dsn)
                if pool is None:
                    try:
                        import psycopg
                        connect = lambda dsn=dsn: psycopg.connect(dsn)
                    except ImportError:
                        import psycopg2
                        connect = lambda dsn=dsn: psycopg2.connect(dsn)
                    pool = _pools[dsn] = ConnectionPool(
                        connect,
                        max_size=int(os.environ.get("SNAPSHOT_DATABASE_POOL_SIZE", "3")),
                    )
            pool.check_connection()
            break
        except Exception as exc:
            last_error = exc
            with _pool_lock:
                _pools.pop(dsn, None)
            pool = None
    if pool is None:
        raise last_error or RuntimeError("Unable to connect to snapshot storage.")
    with pool.connection() as conn:
        yield conn


def initialize_schema() -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SNAPSHOT_DDL)


def pool_health() -> dict:
    with _pool_lock:
        return {f"pool_{index + 1}": pool.stats() for index, pool in enumerate(_pools.values())}


def delete_user_snapshots(user_id: str) -> int:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM custom_analysis_snapshots WHERE user_id = %s", (user_id,))
            return cur.rowcount


def ensure_schema_if_configured() -> bool:
    if not _database_url():
        print("Analysis snapshot schema skipped: no analytics database URL configured.")
        return False
    initialize_schema()
    return True


def save_standard_snapshot(
    analysis_result: dict,
    *,
    analysis_type: AnalysisType = AnalysisType.STANDARD,
    algorithm_version: str = "standard-v1",
    analysis_date: date | None = None,
) -> AnalysisSnapshot | None:
    if analysis_type not in PUBLIC_ANALYSIS_TYPES:
        return None
    if not analysis_result or analysis_result.get("error"):
        return None

    snapshot = AnalysisSnapshot.from_analysis_result(
        analysis_result,
        analysis_date=analysis_date,
        algorithm_version=algorithm_version,
    )
    if not snapshot.ticker:
        return None

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analysis_versions (algorithm_version, description)
                VALUES (%s, %s)
                ON CONFLICT (algorithm_version) DO NOTHING
                """,
                (snapshot.algorithm_version, "Cenvarnstandard algorithm"),
            )
            cur.execute(
                """
                INSERT INTO analysis_snapshots (
                    ticker, company_name, analysis_date, algorithm_version,
                    valuation_score, quality_score, growth_score, momentum_score,
                    risk_score, final_rating, intrinsic_value, market_price,
                    market_fear_score, sector, official_metrics
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id, created_at
                """,
                (
                    snapshot.ticker,
                    snapshot.company_name,
                    snapshot.analysis_date,
                    snapshot.algorithm_version,
                    snapshot.valuation_score,
                    snapshot.quality_score,
                    snapshot.growth_score,
                    snapshot.momentum_score,
                    snapshot.risk_score,
                    snapshot.final_rating,
                    snapshot.intrinsic_value,
                    snapshot.market_price,
                    snapshot.market_fear_score,
                    snapshot.sector,
                    json.dumps(snapshot.official_metrics or {}),
                ),
            )
            row = cur.fetchone()

    return AnalysisSnapshot(
        **{**snapshot.__dict__, "id": row[0], "created_at": row[1]},
    )


def get_company_snapshots_by_slug(slug: str, *, limit: int = 12, offset: int = 0) -> list[AnalysisSnapshot]:
    """Return a paginated official history for an exact normalized company slug."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ON (ticker) ticker, company_name
                   FROM analysis_snapshots
                   ORDER BY ticker, analysis_date DESC, created_at DESC"""
            )
            ticker = next(
                (row[0] for row in cur.fetchall() if company_slug(row[1]) == slug),
                None,
            )
    if not ticker:
        return []
    history = list_ticker_snapshots(ticker, limit=max(1, min(limit + offset, 120)))
    return history[offset:offset + limit]


def save_custom_snapshot(
    user_id: str,
    analysis_result: dict[str, Any],
    *,
    formula_name: str,
    formula_version: str,
    factors: dict[str, float],
    backtest_summary: dict[str, Any] | None = None,
    default_comparison: dict[str, Any] | None = None,
    benchmark_comparison: dict[str, Any] | None = None,
    notes: str = "",
    analysis_date: date | None = None,
) -> CustomAnalysisSnapshot:
    """Append an immutable private custom-model result for one owner."""
    snapshot = CustomAnalysisSnapshot(
        id=uuid.uuid4().hex,
        user_id=user_id,
        ticker=str(analysis_result.get("symbol") or "").upper(),
        company_name=str(analysis_result.get("name") or analysis_result.get("symbol") or ""),
        formula_name=formula_name,
        formula_version=formula_version,
        composite_score=float(analysis_result["composite_score"]) if analysis_result.get("composite_score") is not None else None,
        factors=dict(factors),
        backtest_summary=dict(backtest_summary or {}),
        default_comparison=dict(default_comparison or {}),
        benchmark_comparison=dict(benchmark_comparison or {}),
        notes=notes,
        analysis_date=analysis_date or date.today(),
    )
    if not snapshot.user_id or not snapshot.ticker:
        raise ValueError("user_id and ticker are required")
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO custom_analysis_snapshots (
                    id, user_id, ticker, company_name, formula_name, formula_version,
                    composite_score, factors, backtest_summary, default_comparison,
                    benchmark_comparison, notes, analysis_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
                RETURNING created_at
                """,
                (snapshot.id, snapshot.user_id, snapshot.ticker, snapshot.company_name,
                 snapshot.formula_name, snapshot.formula_version, snapshot.composite_score,
                 json.dumps(snapshot.factors), json.dumps(snapshot.backtest_summary),
                 json.dumps(snapshot.default_comparison), json.dumps(snapshot.benchmark_comparison),
                 snapshot.notes, snapshot.analysis_date),
            )
            created_at = cur.fetchone()[0]
    return CustomAnalysisSnapshot(**{**snapshot.__dict__, "created_at": created_at})


def _custom_from_row(row) -> CustomAnalysisSnapshot:
    return CustomAnalysisSnapshot(
        id=row[0], user_id=row[1], ticker=row[2], company_name=row[3],
        formula_name=row[4], formula_version=row[5], composite_score=row[6],
        factors=row[7] or {}, backtest_summary=row[8] or {},
        default_comparison=row[9] or {}, benchmark_comparison=row[10] or {},
        notes=row[11] or "", analysis_date=row[12], created_at=row[13],
    )


def list_custom_snapshots(user_id: str, ticker: str, *, limit: int = 12, offset: int = 0) -> list[CustomAnalysisSnapshot]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, user_id, ticker, company_name, formula_name,
                          formula_version, composite_score, factors, backtest_summary,
                          default_comparison, benchmark_comparison, notes,
                          analysis_date, created_at
                   FROM custom_analysis_snapshots
                   WHERE user_id = %s AND ticker = %s
                   ORDER BY analysis_date DESC, created_at DESC
                   LIMIT %s OFFSET %s""",
                (user_id, ticker.upper(), limit, offset),
            )
            return [_custom_from_row(row) for row in cur.fetchall()]


def get_custom_snapshot_for_owner(snapshot_id: str, user_id: str) -> CustomAnalysisSnapshot | None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, user_id, ticker, company_name, formula_name,
                          formula_version, composite_score, factors, backtest_summary,
                          default_comparison, benchmark_comparison, notes,
                          analysis_date, created_at
                   FROM custom_analysis_snapshots WHERE id = %s AND user_id = %s""",
                (snapshot_id, user_id),
            )
            row = cur.fetchone()
    return _custom_from_row(row) if row else None


def get_snapshot(ticker: str, yyyymmdd: str) -> AnalysisSnapshot | None:
    analysis_date = datetime.strptime(yyyymmdd, "%Y%m%d").date()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ticker, company_name, analysis_date, algorithm_version,
                       valuation_score, quality_score, growth_score, momentum_score,
                       risk_score, final_rating, intrinsic_value, market_price,
                       market_fear_score, sector, created_at, official_metrics
                FROM analysis_snapshots
                WHERE ticker = %s AND analysis_date = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (ticker.upper(), analysis_date),
            )
            row = cur.fetchone()
    if not row:
        return None
    return AnalysisSnapshot(
        id=row[0],
        ticker=row[1],
        company_name=row[2],
        analysis_date=row[3],
        algorithm_version=row[4],
        valuation_score=row[5],
        quality_score=row[6],
        growth_score=row[7],
        momentum_score=row[8],
        risk_score=row[9],
        final_rating=row[10],
        intrinsic_value=row[11],
        market_price=row[12],
        market_fear_score=row[13],
        sector=row[14] or "",
        created_at=row[15],
        official_metrics=row[16] or {},
    )


def list_ticker_snapshots(ticker: str, limit: int = 24) -> list[AnalysisSnapshot]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (analysis_date)
                       id, ticker, company_name, analysis_date, algorithm_version,
                       valuation_score, quality_score, growth_score, momentum_score,
                       risk_score, final_rating, intrinsic_value, market_price,
                       market_fear_score, sector, created_at, official_metrics
                FROM analysis_snapshots
                WHERE ticker = %s
                ORDER BY analysis_date DESC, created_at DESC, algorithm_version DESC
                LIMIT %s
                """,
                (ticker.upper(), limit),
            )
            rows = cur.fetchall()
    return [
        AnalysisSnapshot(
            id=row[0],
            ticker=row[1],
            company_name=row[2],
            analysis_date=row[3],
            algorithm_version=row[4],
            valuation_score=row[5],
            quality_score=row[6],
            growth_score=row[7],
            momentum_score=row[8],
            risk_score=row[9],
            final_rating=row[10],
            intrinsic_value=row[11],
            market_price=row[12],
            market_fear_score=row[13],
            sector=row[14] or "",
            created_at=row[15],
            official_metrics=row[16] or {},
        )
        for row in rows
    ]


def list_public_snapshots(limit: int = 500) -> list[AnalysisSnapshot]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ticker, company_name, analysis_date, algorithm_version,
                       valuation_score, quality_score, growth_score, momentum_score,
                       risk_score, final_rating, intrinsic_value, market_price,
                       market_fear_score, sector, created_at, official_metrics
                FROM analysis_snapshots
                ORDER BY analysis_date DESC, created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [
        AnalysisSnapshot(
            id=row[0],
            ticker=row[1],
            company_name=row[2],
            analysis_date=row[3],
            algorithm_version=row[4],
            valuation_score=row[5],
            quality_score=row[6],
            growth_score=row[7],
            momentum_score=row[8],
            risk_score=row[9],
            final_rating=row[10],
            intrinsic_value=row[11],
            market_price=row[12],
            market_fear_score=row[13],
            sector=row[14] or "",
            created_at=row[15],
            official_metrics=row[16] or {},
        )
        for row in rows
    ]


def _snapshot_from_row(row) -> AnalysisSnapshot:
    return AnalysisSnapshot(
        id=row[0],
        ticker=row[1],
        company_name=row[2],
        analysis_date=row[3],
        algorithm_version=row[4],
        valuation_score=row[5],
        quality_score=row[6],
        growth_score=row[7],
        momentum_score=row[8],
        risk_score=row[9],
        final_rating=row[10],
        intrinsic_value=row[11],
        market_price=row[12],
        market_fear_score=row[13],
        sector=row[14] or "",
        created_at=row[15],
        official_metrics=row[16] or {},
    )


def list_related_snapshots(snapshot: AnalysisSnapshot, limit: int = 5) -> dict[str, list[AnalysisSnapshot]]:
    """Return SEO link targets from the latest public snapshots.

    Links are intentionally based only on stored STANDARD snapshots so public
    pages do not expose user-specific or experimental analysis data.
    """
    sector = (snapshot.sector or "").strip()
    params = {
        "ticker": snapshot.ticker.upper(),
        "sector": sector,
        "limit": limit,
    }
    base_select = """
        WITH latest AS (
            SELECT DISTINCT ON (ticker)
                   id, ticker, company_name, analysis_date, algorithm_version,
                   valuation_score, quality_score, growth_score, momentum_score,
                   risk_score, final_rating, intrinsic_value, market_price,
                   market_fear_score, sector, created_at, official_metrics
            FROM analysis_snapshots
            WHERE ticker <> %(ticker)s
            ORDER BY ticker, analysis_date DESC, created_at DESC
        )
    """

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                base_select  # nosec B608
                + """
                SELECT *
                FROM latest
                ORDER BY
                    ABS(COALESCE(valuation_score, 0) - %(valuation_score)s)
                    + ABS(COALESCE(quality_score, 0) - %(quality_score)s)
                    + ABS(COALESCE(growth_score, 0) - %(growth_score)s)
                    + ABS(COALESCE(momentum_score, 0) - %(momentum_score)s)
                    + ABS(COALESCE(risk_score, 0) - %(risk_score)s),
                    analysis_date DESC
                LIMIT %(limit)s
                """,
                {
                    **params,
                    "valuation_score": snapshot.valuation_score or 0,
                    "quality_score": snapshot.quality_score or 0,
                    "growth_score": snapshot.growth_score or 0,
                    "momentum_score": snapshot.momentum_score or 0,
                    "risk_score": snapshot.risk_score or 0,
                },
            )
            similar = [_snapshot_from_row(row) for row in cur.fetchall()]

            competitors = []
            if sector:
                cur.execute(
                    base_select  # nosec B608
                    + """
                    SELECT *
                    FROM latest
                    WHERE sector = %(sector)s
                    ORDER BY analysis_date DESC, valuation_score DESC NULLS LAST
                    LIMIT %(limit)s
                    """,
                    params,
                )
                competitors = [_snapshot_from_row(row) for row in cur.fetchall()]

            cur.execute(
                base_select  # nosec B608
                + """
                SELECT DISTINCT ON (sector) *
                FROM latest
                WHERE COALESCE(sector, '') <> ''
                  AND (%(sector)s = '' OR sector <> %(sector)s)
                ORDER BY sector, analysis_date DESC, valuation_score DESC NULLS LAST
                LIMIT %(limit)s
                """,
                params,
            )
            sectors = [_snapshot_from_row(row) for row in cur.fetchall()]

    return {
        "similar_factor_stocks": similar,
        "industry_competitors": competitors,
        "related_market_sectors": sectors,
    }
