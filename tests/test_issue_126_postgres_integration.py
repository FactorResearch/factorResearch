"""Disposable PostgreSQL process tests for ISSUE_126 migration safety.

Set ``ISSUE126_POSTGRES_URL`` to an administrator URL for a disposable server.
Each test creates and removes its own database; the suite never targets a named
application database.
"""

from __future__ import annotations

import multiprocessing
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from codes.data import db, migrate, temporal
from codes.data.migrations import (
    MigrationLockTimeoutError,
    _advisory_lock_key,
    apply_migrations,
    verify_migrations,
)

pytestmark = pytest.mark.live_network


def _admin_url() -> str:
    """Return the explicitly authorized disposable PostgreSQL administrator URL."""
    url = os.environ.get("ISSUE126_POSTGRES_URL", "").strip()
    if not url:
        pytest.skip("ISSUE126_POSTGRES_URL is required for disposable PostgreSQL tests")
    return url


@contextmanager
def _temporary_database() -> Iterator[str]:
    """Create one isolated database and force-remove it after the test."""
    admin_url = _admin_url()
    database_name = f"issue126_{uuid.uuid4().hex}"
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    database_url = make_conninfo(admin_url, dbname=database_name)
    try:
        yield database_url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def _migrate_users(database_url: str, outcomes: multiprocessing.Queue) -> None:
    """Run one release process and return only its sanitized outcome category."""
    try:
        db.init_user_db(database_url, lock_timeout_seconds=5.0)
    except Exception as exc:  # pragma: no cover - asserted through child exit data
        outcomes.put(type(exc).__name__)
    else:
        outcomes.put("ok")


def _verify_users(database_url: str, outcomes: multiprocessing.Queue) -> None:
    """Run one runtime readiness process and return its sanitized outcome."""
    try:
        with psycopg.connect(database_url) as connection:
            verify_migrations(
                connection,
                "users",
                required_tables=db._USERS_REQUIRED_TABLES,
            )
    except Exception as exc:  # pragma: no cover - asserted through child exit data
        outcomes.put(type(exc).__name__)
    else:
        outcomes.put("ok")


def test_two_release_processes_initialize_empty_users_database_once() -> None:
    """Two cold-start release processes serialize without duplicate migration rows."""
    with _temporary_database() as database_url:
        outcomes: multiprocessing.Queue = multiprocessing.Queue()
        processes = [
            multiprocessing.Process(target=_migrate_users, args=(database_url, outcomes))
            for _ in range(2)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=15)

        assert [outcomes.get(timeout=1) for _ in processes] == ["ok", "ok"]
        assert all(process.exitcode == 0 for process in processes)
        with psycopg.connect(database_url) as connection:
            rows = connection.execute(
                "SELECT migration, COUNT(*) FROM schema_migrations "
                "WHERE scope = 'users' GROUP BY migration ORDER BY migration"
            ).fetchall()
            assert rows == [
                ("001_issue_063_sync_metadata_users.sql", 1),
                ("002_issue_064_idempotency_users.sql", 1),
            ]
            verify_migrations(
                connection,
                "users",
                required_tables=db._USERS_REQUIRED_TABLES,
            )


def test_market_and_analytics_release_scopes_bootstrap_and_verify() -> None:
    """The complete non-user release DDL compiles and satisfies runtime checks."""
    with _temporary_database() as database_url:
        db.init_db(
            database_url,
            additional_bootstrap_sql=(temporal.SCHEMA,),
            lock_timeout_seconds=5.0,
        )
        migrate._initialize_analytics_schema(database_url, lock_timeout_seconds=5.0)

        with psycopg.connect(database_url) as connection:
            verify_migrations(
                connection,
                "market",
                required_tables=db._MARKET_REQUIRED_TABLES,
            )
            verify_migrations(
                connection,
                "analytics",
                required_tables=(
                    "analytics_events",
                    "analysis_snapshots",
                    "analysis_versions",
                    "custom_analysis_snapshots",
                ),
            )


def test_interrupted_transaction_rolls_back_ddl_and_recovers() -> None:
    """Rollback after DDL removes partial state and a rerun commits cleanly."""
    with _temporary_database() as database_url:
        connection = psycopg.connect(database_url)
        apply_migrations(
            connection,
            "interruption_test",
            bootstrap_sql="CREATE TABLE interruption_probe (id INTEGER PRIMARY KEY)",
        )
        connection.rollback()
        connection.close()

        with psycopg.connect(database_url) as verification:
            assert verification.execute("SELECT to_regclass('interruption_probe')").fetchone() == (
                None,
            )

        with psycopg.connect(database_url) as recovery:
            apply_migrations(
                recovery,
                "interruption_test",
                bootstrap_sql="CREATE TABLE interruption_probe (id INTEGER PRIMARY KEY)",
            )
        with psycopg.connect(database_url) as verification:
            assert verification.execute("SELECT to_regclass('interruption_probe')").fetchone() == (
                "interruption_probe",
            )


def test_multiple_runtime_processes_reject_partial_schema_without_mutation() -> None:
    """Concurrent normal processes fail closed against release state missing tables."""
    with _temporary_database() as database_url:
        with psycopg.connect(database_url) as connection:
            connection.execute(
                """
                CREATE TABLE schema_migrations (
                    scope TEXT NOT NULL,
                    migration TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (scope, migration)
                )
                """
            )

        outcomes: multiprocessing.Queue = multiprocessing.Queue()
        processes = [
            multiprocessing.Process(target=_verify_users, args=(database_url, outcomes))
            for _ in range(4)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=10)

        assert [outcomes.get(timeout=1) for _ in processes] == [
            "DatabaseNotReadyError"
        ] * 4
        with psycopg.connect(database_url) as connection:
            tables = connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            ).fetchall()
            assert tables == [("schema_migrations",)]


def test_lock_timeout_and_insufficient_privilege_fail_closed() -> None:
    """Contention and a runtime-like role both fail without partial schema writes."""
    with _temporary_database() as database_url:
        owner = psycopg.connect(database_url)
        owner.execute(
            "SELECT pg_advisory_xact_lock(%(lock_key)s)",
            {"lock_key": _advisory_lock_key("locked_scope")},
        )
        contender = psycopg.connect(database_url)
        with pytest.raises(MigrationLockTimeoutError):
            apply_migrations(contender, "locked_scope", lock_timeout_seconds=0.05)
        contender.rollback()
        contender.close()
        owner.rollback()

        role_name = f"issue126_runtime_{uuid.uuid4().hex}"
        with psycopg.connect(_admin_url(), autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE ROLE {}").format(sql.Identifier(role_name)))
        try:
            restricted = psycopg.connect(database_url)
            restricted.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role_name)))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                apply_migrations(restricted, "restricted_scope", lock_timeout_seconds=0.1)
            restricted.rollback()
            restricted.close()
        finally:
            with psycopg.connect(_admin_url(), autocommit=True) as admin:
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role_name)))
