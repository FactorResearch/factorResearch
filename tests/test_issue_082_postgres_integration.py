"""Disposable PostgreSQL permission proof for ISSUE_082.

Set ``ISSUE082_POSTGRES_URL`` to an administrator URL for a disposable cluster.
The test creates temporary databases and LOGIN principals, applies the checked-in
role scripts and migrations, proves workload isolation, and drops its artifacts.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from codes.core.database_roles import DatabaseWorkload, verify_database_role
from codes.data import db, migrate


def _admin_url() -> str:
    """Return the explicitly configured disposable-cluster administrator URL."""

    url = os.environ.get("ISSUE082_POSTGRES_URL", "").strip()
    if not url:
        pytest.skip("ISSUE082_POSTGRES_URL is required for disposable PostgreSQL tests")
    return url


def _connection_url(base_url: str, *, database: str, user: str, password: str) -> str:
    """Build one test URL without exposing credentials in assertion output."""

    parameters = conninfo_to_dict(base_url)
    parameters.update(dbname=database, user=user, password=password)
    return make_conninfo(**parameters)


def _execute_file(connection: psycopg.Connection, path: str) -> None:
    """Execute one trusted repository SQL artifact in the caller's transaction."""

    connection.execute(Path(path).read_text(encoding="utf-8"))


def test_postgresql_roles_enforce_workload_and_tenant_boundaries() -> None:
    """Real PostgreSQL denies DDL, cross-tenant, worker, and read-only escalation."""

    admin_url = _admin_url()
    suffix = uuid.uuid4().hex[:10]
    users_database = f"issue082_users_{suffix}"
    market_database = f"issue082_market_{suffix}"
    analytics_database = f"issue082_analytics_{suffix}"
    password = uuid.uuid4().hex
    logins = {
        DatabaseWorkload.APP: f"issue082_app_{suffix}",
        DatabaseWorkload.SERVICE: f"issue082_service_{suffix}",
        DatabaseWorkload.MIGRATION: f"issue082_migration_{suffix}",
        DatabaseWorkload.MARKET_WORKER: f"issue082_worker_{suffix}",
        DatabaseWorkload.READONLY: f"issue082_readonly_{suffix}",
    }

    admin_parameters = conninfo_to_dict(admin_url)
    admin_database = str(admin_parameters.get("dbname") or "postgres")
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            _execute_file(admin, "deploy/postgresql/001_canonical_roles.sql")
            for database_name in (users_database, market_database, analytics_database):
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
            for workload, login in logins.items():
                admin.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(sql.Identifier(login), sql.Literal(password))
                )
                admin.execute(
                    sql.SQL("GRANT {} TO {}").format(
                        sql.Identifier(workload.value),
                        sql.Identifier(login),
                    )
                )

        users_admin_url = make_conninfo(**{**admin_parameters, "dbname": users_database})
        market_admin_url = make_conninfo(**{**admin_parameters, "dbname": market_database})
        analytics_admin_url = make_conninfo(**{**admin_parameters, "dbname": analytics_database})
        with psycopg.connect(users_admin_url) as users_admin:
            _execute_file(users_admin, "deploy/postgresql/002_users_database_access.sql")
        with psycopg.connect(market_admin_url) as market_admin:
            _execute_file(market_admin, "deploy/postgresql/003_market_database_access.sql")
        with psycopg.connect(analytics_admin_url) as analytics_admin:
            _execute_file(analytics_admin, "deploy/postgresql/004_analytics_database_access.sql")

        migration_users_url = _connection_url(
            admin_url,
            database=users_database,
            user=logins[DatabaseWorkload.MIGRATION],
            password=password,
        )
        migration_market_url = _connection_url(
            admin_url,
            database=market_database,
            user=logins[DatabaseWorkload.MIGRATION],
            password=password,
        )
        migration_analytics_url = _connection_url(
            admin_url,
            database=analytics_database,
            user=logins[DatabaseWorkload.MIGRATION],
            password=password,
        )
        db.init_user_db(migration_users_url)
        db.init_db(migration_market_url)
        migrate._initialize_analytics_schema(
            migration_market_url,
            lock_timeout_seconds=5.0,
        )
        migrate._initialize_analytics_schema(
            migration_analytics_url,
            lock_timeout_seconds=5.0,
        )

        urls = {
            workload: _connection_url(
                admin_url,
                database=users_database,
                user=login,
                password=password,
            )
            for workload, login in logins.items()
        }
        with psycopg.connect(migration_users_url) as migration:
            verify_database_role(migration, DatabaseWorkload.MIGRATION)
        with psycopg.connect(urls[DatabaseWorkload.APP]) as app:
            verify_database_role(app, DatabaseWorkload.APP)
            db._verify_users_service_policies(app)
            db._verify_users_table_privileges(app, DatabaseWorkload.APP)
            app.execute("SELECT set_config('app.current_user_id', 'alice', true)")
            app.execute("INSERT INTO user_settings (user_id) VALUES ('alice')")
            app.commit()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                app.execute("CREATE TABLE forbidden_app_ddl (id integer)")
            app.rollback()
            app.execute("SELECT set_config('app.current_user_id', 'bob', true)")
            assert app.execute("SELECT user_id FROM user_settings").fetchall() == []
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                app.execute(
                    "INSERT INTO waitlist_signups (email, source) VALUES ('x@example.test', 'test')"
                )

        with psycopg.connect(urls[DatabaseWorkload.SERVICE]) as service:
            verify_database_role(service, DatabaseWorkload.SERVICE)
            db._verify_users_table_privileges(service, DatabaseWorkload.SERVICE)
            assert service.execute(
                "SELECT user_id FROM user_settings WHERE user_id = 'alice'"
            ).fetchone() == ("alice",)
            service.execute(
                "INSERT INTO waitlist_signups (email, source) VALUES ('x@example.test', 'test')"
            )

        with pytest.raises(psycopg.OperationalError, match="permission denied"):
            psycopg.connect(urls[DatabaseWorkload.MARKET_WORKER])

        market_urls = {
            workload: _connection_url(
                admin_url,
                database=market_database,
                user=login,
                password=password,
            )
            for workload, login in logins.items()
        }
        with psycopg.connect(market_urls[DatabaseWorkload.MARKET_WORKER]) as worker:
            verify_database_role(worker, DatabaseWorkload.MARKET_WORKER)
            worker.execute(
                "INSERT INTO value_metrics (ticker, updated_at) VALUES ('TEST', '2026-07-21')"
            )
            worker.commit()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                worker.execute("SELECT event_name FROM analytics_events")
        with psycopg.connect(market_urls[DatabaseWorkload.READONLY]) as readonly:
            verify_database_role(readonly, DatabaseWorkload.READONLY)
            assert readonly.execute("SELECT ticker FROM value_metrics").fetchone() == ("TEST",)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                readonly.execute("DELETE FROM value_metrics")
            readonly.rollback()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                readonly.execute("SELECT event_name FROM analytics_events")

        analytics_urls = {
            workload: _connection_url(
                admin_url,
                database=analytics_database,
                user=login,
                password=password,
            )
            for workload, login in logins.items()
        }
        with psycopg.connect(analytics_urls[DatabaseWorkload.APP]) as analytics_app:
            verify_database_role(analytics_app, DatabaseWorkload.APP)
            analytics_app.execute(
                "INSERT INTO analytics_events (event_name) VALUES ('issue082_test')"
            )
        with psycopg.connect(analytics_urls[DatabaseWorkload.READONLY]) as analytics_readonly:
            verify_database_role(analytics_readonly, DatabaseWorkload.READONLY)
            assert analytics_readonly.execute(
                "SELECT migration FROM schema_migrations ORDER BY migration"
            ).fetchall()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                analytics_readonly.execute("SELECT event_name FROM analytics_events")
        with pytest.raises(psycopg.OperationalError, match="permission denied"):
            psycopg.connect(analytics_urls[DatabaseWorkload.MARKET_WORKER])
    finally:
        db._pools.clear()
        with psycopg.connect(admin_url, autocommit=True) as admin:
            for database_name in (users_database, market_database, analytics_database):
                admin.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                        sql.Identifier(database_name)
                    )
                )
            for login in logins.values():
                admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(login)))

        assert admin_database
