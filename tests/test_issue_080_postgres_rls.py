"""Fast contracts for ISSUE_080's PostgreSQL tenant boundary."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from codes.data import db
from codes.data.migrations import DatabaseNotReadyError


class _Result:
    """Return one deterministic row from a fake Psycopg execution."""

    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _Connection:
    """Capture SQL issued through the narrow users connection contract."""

    def __init__(self, rows=None):
        self.calls = []
        self._rows = list(rows or [])

    def execute(self, statement, params=None):
        self.calls.append((statement, params))
        row = self._rows.pop(0) if self._rows else None
        return _Result(row)


class _Pool:
    """Expose one reusable fake connection through the production pool shape."""

    def __init__(self, connection):
        self._connection = connection

    @contextmanager
    def connection(self):
        yield self._connection


def test_migration_secures_every_registered_user_owned_table() -> None:
    migration = Path("migrations/004_issue_080_user_owned_rls_users.sql").read_text()

    for table_name, owner_column in db._USER_OWNED_TABLES:
        assert f"('{table_name}', '{owner_column}')" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_user_id" in migration
    assert "NULLIF(current_setting" in migration
    assert "FROM pg_policies" in migration


def test_users_connection_requires_exactly_one_access_mode(monkeypatch) -> None:
    connection = _Connection()
    monkeypatch.setattr(db, "_pool", lambda _url: _Pool(connection))
    monkeypatch.setattr(db, "_users_db_url", lambda: "postgresql://runtime")

    with pytest.raises(ValueError, match="exactly one"):
        with db._users_conn():
            pass
    with pytest.raises(ValueError, match="exactly one"):
        with db._users_conn("alice", privileged=True):
            pass

    with db._users_conn(" auth0|alice "):
        pass

    statement, params = connection.calls[0]
    assert "app.current_user_id" in statement
    assert "true" in statement
    assert params == {"user_id": "auth0|alice"}


def test_privileged_connection_uses_service_url_without_tenant_setting(monkeypatch) -> None:
    connection = _Connection()
    selected_urls = []
    monkeypatch.setattr(
        db,
        "_pool",
        lambda url: selected_urls.append(url) or _Pool(connection),
    )
    monkeypatch.setattr(db, "_users_service_db_url", lambda: "postgresql://service")

    with db._users_conn(privileged=True):
        pass

    assert selected_urls == ["postgresql://service"]
    assert connection.calls == []


def test_production_rejects_reused_users_service_credential(monkeypatch) -> None:
    monkeypatch.setattr(db, "is_production", lambda: True)
    monkeypatch.setattr(
        db,
        "_users_db_url",
        lambda: "postgresql://runtime@users/database",
    )
    monkeypatch.setenv(
        "DATABASE_USERS_SERVICE_URL",
        "postgresql://runtime@users/database?application_name=service",
    )

    with pytest.raises(RuntimeError, match="credentials distinct"):
        db._users_service_db_url()


def test_rls_verification_fails_closed_and_logs_each_table(caplog) -> None:
    caplog.set_level("INFO")
    secure_rows = [(True, True, True)] * len(db._USER_OWNED_TABLES)
    connection = _Connection(secure_rows)

    db._verify_users_rls(connection)

    assert len(connection.calls) == len(db._USER_OWNED_TABLES)
    assert "policy verified" in caplog.text

    insecure = _Connection([(True, False, True)])
    with pytest.raises(DatabaseNotReadyError, match="user_weights"):
        db._verify_users_rls(insecure)


def test_production_rejects_superuser_or_bypassrls_runtime(monkeypatch) -> None:
    monkeypatch.setattr(db, "is_production", lambda: True)

    for role_row in (("app", True, False), ("app", False, True)):
        with pytest.raises(RuntimeError, match="superuser or have BYPASSRLS"):
            db._verify_runtime_users_role(_Connection([role_row]))

    db._verify_runtime_users_role(_Connection([("app", False, False)]))
