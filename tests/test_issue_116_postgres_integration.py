"""Disposable PostgreSQL acceptance drills for ISSUE_116.

Set ``ISSUE116_POSTGRES_URL`` (or ``ISSUE126_POSTGRES_URL``) to an administrator
URL. Every test creates and force-removes a uniquely named database.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
import pytest
from cryptography.fernet import Fernet
from psycopg import sql
from psycopg.conninfo import make_conninfo

from codes import portfolio
from codes.data import cache, db, portfolio_repository

pytestmark = pytest.mark.live_network


def _admin_url() -> str:
    url = (
        os.environ.get("ISSUE116_POSTGRES_URL", "").strip()
        or os.environ.get("ISSUE126_POSTGRES_URL", "").strip()
    )
    if not url:
        pytest.skip("ISSUE116_POSTGRES_URL is required for disposable PostgreSQL tests")
    return url


@contextmanager
def _temporary_database() -> Iterator[str]:
    admin_url = _admin_url()
    name = f"issue116_{uuid.uuid4().hex}"
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = make_conninfo(admin_url, dbname=name)
    try:
        yield url
    finally:
        db._pools.clear()
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


@contextmanager
def _postgres_backend(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    role_name = f"issue116_runtime_{uuid.uuid4().hex}"
    try:
        with _temporary_database() as database_url:
            db.init_user_db(database_url, lock_timeout_seconds=5.0)
            with psycopg.connect(database_url) as owner:
                owner.execute(sql.SQL("CREATE ROLE {}").format(sql.Identifier(role_name)))
                owner.execute(
                    sql.SQL(
                        "GRANT SELECT ON schema_migrations, user_weights, subscriptions, "
                        "user_settings, user_usage, waitlist_signups, idempotency_records TO {}"
                    ).format(sql.Identifier(role_name))
                )
            db.configure_users_runtime_role(database_url, role_name)
            runtime_url = make_conninfo(database_url, options=f"-c role={role_name}")
            db._pools.clear()
            db._users_initialized = False
            monkeypatch.setenv("DATABASE_USERS_URL", runtime_url)
            monkeypatch.setenv("DATABASE_USERS_SERVICE_URL", database_url)
            monkeypatch.setenv("PORTFOLIO_STORAGE_BACKEND", "postgres")
            yield runtime_url
    finally:
        with psycopg.connect(_admin_url(), autocommit=True) as admin:
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role_name)))


def test_multi_connection_visibility_rls_concurrency_and_simulation(monkeypatch) -> None:
    with _postgres_backend(monkeypatch) as database_url:
        created = portfolio.create_portfolio("user-1", "Core")
        created, error = portfolio.add_holding("user-1", "Core", "AAPL", 5, 100, "Apple")
        assert error == ""

        with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as other:
            other.execute("SELECT set_config('app.current_user_id', 'user-1', true)")
            assert other.execute("SELECT name FROM portfolios").fetchall() == [{"name": "Core"}]
            other.execute("SELECT set_config('app.current_user_id', 'user-2', true)")
            assert other.execute("SELECT name FROM portfolios").fetchall() == []
            assert other.execute("SELECT symbol FROM portfolio_holdings").fetchall() == []

        assert portfolio.list_portfolios("user-2") == []
        stale = dict(created)
        current = portfolio.load_portfolio("user-1", "Core")
        current["name"] = "Current"
        portfolio.save_portfolio("user-1", current)
        stale["name"] = "Stale"
        with pytest.raises(RuntimeError, match="version conflict"):
            portfolio.save_portfolio("user-1", stale)

        current = portfolio.load_portfolio("user-1", "Current")
        result = {
            "portfolio_name": "Current",
            "holdings": current["holdings"],
            "backtest": {},
            "montecarlo": {},
        }
        portfolio_repository.save_simulation("user-1", current, result)
        assert portfolio_repository.load_simulation("user-1", current) == result
        portfolio_repository.invalidate_simulations("user-1", "Current")
        assert portfolio_repository.load_simulation("user-1", current) is None


def test_tombstones_erasure_and_idempotent_legacy_import(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    cache._encryptor = None
    monkeypatch.setenv("PORTFOLIO_STORAGE_BACKEND", "cache")
    portfolio.create_portfolio("user-1", "Legacy")

    with _postgres_backend(monkeypatch) as database_url:
        first = portfolio.migrate_legacy_user("user-1", purge_files=False)
        second = portfolio.migrate_legacy_user("user-1", purge_files=False)
        assert first["imported"] == ["Legacy"]
        assert second["imported"] == []
        assert second["skipped"]

        portfolio.delete_portfolio("user-1", "Legacy")
        changes = portfolio.list_portfolio_changes("user-1")
        assert changes[0]["deleted_at"]
        exported = portfolio.export_user_data("user-1")
        assert exported["portfolios"][0]["deleted_at"]
        assert exported["tombstones"][0]["name"] == "Legacy"
        assert exported["legacy_imports"][0]["status"] == "completed"
        assert exported["legacy_portfolio_files"][0]["payload"]["name"] == "Legacy"
        evidence = portfolio.delete_all_user_data("user-1")
        assert evidence["database_records"]["portfolio_tombstones"] == 1
        assert evidence["database_records"]["portfolios"] == 1

        with psycopg.connect(database_url) as connection:
            connection.execute("SELECT set_config('app.current_user_id', 'user-1', true)")
            for table in (
                "portfolios",
                "portfolio_holdings",
                "portfolio_transactions",
                "portfolio_tombstones",
                "portfolio_simulation_results",
                "portfolio_legacy_imports",
            ):
                assert connection.execute(
                    sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
                ).fetchone() == (0,)
        assert cache.list_keys("portfolio") == []
    cache._encryptor = None


def test_all_user_tables_use_provider_neutral_rls_and_pool_local_identity(monkeypatch) -> None:
    with _postgres_backend(monkeypatch) as database_url:
        identities = (
            "auth0|alice",
            "clerk_bob",
            "550e8400-e29b-41d4-a716-446655440000",
            "dev-persona:analyst",
        )
        for user_id in identities:
            db.upsert_user_settings(
                user_id,
                {"provider_identity": user_id, "_sync": {"version": 1}},
            )
            assert db.get_user_settings(user_id)["provider_identity"] == user_id

        with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as alice:
            role = alice.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            ).fetchone()
            assert role == {"rolsuper": False, "rolbypassrls": False}
            alice.execute(
                "SELECT set_config('app.current_user_id', %(user_id)s, true)",
                {"user_id": identities[0]},
            )
            assert alice.execute("SELECT user_id FROM user_settings").fetchall() == [
                {"user_id": identities[0]}
            ]
            assert (
                alice.execute(
                    "DELETE FROM user_settings WHERE user_id = %(user_id)s",
                    {"user_id": identities[1]},
                ).rowcount
                == 0
            )

        with psycopg.connect(database_url) as alice:
            alice.execute(
                "SELECT set_config('app.current_user_id', %(user_id)s, true)",
                {"user_id": identities[0]},
            )
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                alice.execute(
                    "UPDATE user_settings SET user_id = %(other_user)s WHERE user_id = %(user_id)s",
                    {"other_user": identities[1], "user_id": identities[0]},
                )
            alice.rollback()

        with psycopg.connect(database_url) as alice:
            alice.execute(
                "SELECT set_config('app.current_user_id', %(user_id)s, true)",
                {"user_id": identities[0]},
            )
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                alice.execute(
                    "INSERT INTO user_settings (user_id, settings_json) "
                    "VALUES (%(other_user)s, '{}'::jsonb)",
                    {"other_user": "clerk_mallory"},
                )
            alice.rollback()

        with db._users_conn(identities[0]) as alice:
            pid_row = alice.execute("SELECT pg_backend_pid()").fetchone()
            alice_pid = pid_row.get("pg_backend_pid") if isinstance(pid_row, dict) else pid_row[0]
            setting_row = alice.execute(
                "SELECT current_setting('app.current_user_id', true)"
            ).fetchone()
            setting = (
                setting_row.get("current_setting")
                if isinstance(setting_row, dict)
                else setting_row[0]
            )
            assert setting == identities[0]
        with db._pool(db._users_db_url()).connection() as unscoped:
            pid_row = unscoped.execute("SELECT pg_backend_pid()").fetchone()
            assert (
                pid_row.get("pg_backend_pid") if isinstance(pid_row, dict) else pid_row[0]
            ) == alice_pid
            setting_row = unscoped.execute(
                "SELECT current_setting('app.current_user_id', true)"
            ).fetchone()
            setting = (
                setting_row.get("current_setting")
                if isinstance(setting_row, dict)
                else setting_row[0]
            )
            assert setting in (None, "")
        with db._users_conn(identities[1]) as bob:
            pid_row = bob.execute("SELECT pg_backend_pid()").fetchone()
            assert (
                pid_row.get("pg_backend_pid") if isinstance(pid_row, dict) else pid_row[0]
            ) == alice_pid
            rows = bob.execute("SELECT user_id FROM user_settings").fetchall()
            assert [row.get("user_id") if isinstance(row, dict) else row[0] for row in rows] == [
                identities[1]
            ]

        db.upsert_subscription(
            identities[0],
            plan="premium",
            status="active",
            stripe_customer_id="cus_issue080",
            privileged=True,
        )
        assert db.get_subscription_by_customer("cus_issue080")["user_id"] == identities[0]
        deleted = db.delete_user_records(identities[0])
        assert deleted["subscriptions"] == 1
        assert deleted["user_settings"] == 1
