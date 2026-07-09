from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterator

from codes.models.analysis_snapshot import (
    AnalysisSnapshot,
    AnalysisType,
    PUBLIC_ANALYSIS_TYPES,
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (ticker, analysis_date, algorithm_version)
);

CREATE TABLE IF NOT EXISTS analysis_versions (
    algorithm_version TEXT PRIMARY KEY,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def _database_url() -> str | None:
    return (
        os.environ.get("ANALYTICS_DATABASE_URL")
        or os.environ.get("FACTORRESEARCH_ANALYTICS_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
    )


@contextmanager
def _connect() -> Iterator:
    dsn = _database_url()
    if not dsn:
        raise RuntimeError("ANALYTICS_DATABASE_URL or DATABASE_URL is required for analysis snapshots.")

    try:
        import psycopg

        conn = psycopg.connect(dsn)
    except ImportError:
        import psycopg2

        conn = psycopg2.connect(dsn)

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_schema() -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SNAPSHOT_DDL)


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

    initialize_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analysis_versions (algorithm_version, description)
                VALUES (%s, %s)
                ON CONFLICT (algorithm_version) DO NOTHING
                """,
                (snapshot.algorithm_version, "FactorResearch standard algorithm"),
            )
            cur.execute(
                """
                INSERT INTO analysis_snapshots (
                    ticker, company_name, analysis_date, algorithm_version,
                    valuation_score, quality_score, growth_score, momentum_score,
                    risk_score, final_rating, intrinsic_value, market_price,
                    market_fear_score
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, analysis_date, algorithm_version)
                DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    valuation_score = EXCLUDED.valuation_score,
                    quality_score = EXCLUDED.quality_score,
                    growth_score = EXCLUDED.growth_score,
                    momentum_score = EXCLUDED.momentum_score,
                    risk_score = EXCLUDED.risk_score,
                    final_rating = EXCLUDED.final_rating,
                    intrinsic_value = EXCLUDED.intrinsic_value,
                    market_price = EXCLUDED.market_price,
                    market_fear_score = EXCLUDED.market_fear_score
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
                ),
            )
            row = cur.fetchone()

    return AnalysisSnapshot(
        **{**snapshot.__dict__, "id": row[0], "created_at": row[1]},
    )


def get_snapshot(ticker: str, yyyymmdd: str) -> AnalysisSnapshot | None:
    analysis_date = datetime.strptime(yyyymmdd, "%Y%m%d").date()
    initialize_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ticker, company_name, analysis_date, algorithm_version,
                       valuation_score, quality_score, growth_score, momentum_score,
                       risk_score, final_rating, intrinsic_value, market_price,
                       market_fear_score, created_at
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
        created_at=row[14],
    )


def list_public_snapshots(limit: int = 500) -> list[AnalysisSnapshot]:
    initialize_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ticker, company_name, analysis_date, algorithm_version,
                       valuation_score, quality_score, growth_score, momentum_score,
                       risk_score, final_rating, intrinsic_value, market_price,
                       market_fear_score, created_at
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
            created_at=row[14],
        )
        for row in rows
    ]
