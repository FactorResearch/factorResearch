"""Regression tests for serialized release migrations and runtime readiness."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from codes.data import db, migrate, migrations


class _Result:
    """Provide the minimal Psycopg result contract used by migration tests."""

    def __init__(self, *, one: object = None, all_rows: list[object] | None = None) -> None:
        self._one = one
        self._all = all_rows or []

    def fetchone(self) -> object:
        """Return the configured single-row result."""
        return self._one

    def fetchall(self) -> list[object]:
        """Return configured rows without sharing mutable state."""
        return list(self._all)


class _MigrationConnection:
    """Record SQL and emulate one uninitialized PostgreSQL migration scope."""

    def __init__(self, *, lock_results: list[bool] | None = None, checksum: str | None = None) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._lock_results = iter(lock_results or [True])
        self._checksum = checksum

    def execute(self, sql: str, params: dict[str, object] | None = None) -> _Result:
        """Return deterministic rows for lock and checksum statements."""
        normalized = " ".join(sql.split())
        values = params or {}
        self.calls.append((normalized, values))
        if "pg_try_advisory_xact_lock" in normalized:
            return _Result(one=(next(self._lock_results),))
        if normalized.startswith("SELECT checksum"):
            return _Result(one=(self._checksum,) if self._checksum is not None else None)
        return _Result()


class _ReadinessConnection:
    """Emulate PostgreSQL catalog and migration-state reads without writes."""

    def __init__(
        self,
        *,
        missing_table: str | None = None,
        migration_rows: list[object] | None = None,
    ) -> None:
        self.missing_table = missing_table
        self.migration_rows = migration_rows or []
        self.statements: list[str] = []

    def execute(self, sql: str, params: dict[str, object] | None = None) -> _Result:
        """Resolve table presence and recorded migrations from configured state."""
        normalized = " ".join(sql.split())
        self.statements.append(normalized)
        if "to_regclass" in normalized:
            table = str((params or {})["table"])
            return _Result(one=(None if table == self.missing_table else table,))
        if normalized.startswith("SELECT migration, checksum"):
            return _Result(all_rows=self.migration_rows)
        raise AssertionError(f"Unexpected readiness SQL: {normalized}")


def _write_migration(root: Path, name: str = "001_example.sql") -> Path:
    """Create one deterministic migration fixture below a temporary root."""
    path = root / name
    path.write_text("CREATE TABLE example (id INTEGER);\n", encoding="utf-8")
    return path


def test_apply_migrations_locks_before_bootstrap_and_records_checksum(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The serialized transaction must lock before inspecting or changing state."""
    migration = _write_migration(tmp_path, "001_example.sql")
    monkeypatch.setattr(migrations, "_MIGRATIONS_ROOT", tmp_path)
    connection = _MigrationConnection()

    applied = migrations.apply_migrations(
        connection,
        "example",
        bootstrap_sql="CREATE TABLE base (id INTEGER);",
    )

    statements = [sql for sql, _ in connection.calls]
    assert applied == 1
    assert "pg_try_advisory_xact_lock" in statements[0]
    assert statements.index("CREATE TABLE base (id INTEGER);") < statements.index(
        migration.read_text(encoding="utf-8").strip()
    )
    insert_index = next(
        index for index, statement in enumerate(statements) if statement.startswith("INSERT INTO schema_migrations")
    )
    assert connection.calls[insert_index][1]["checksum"] == migrations._checksum(migration)


def test_migration_lock_timeout_is_bounded_without_state_reads() -> None:
    """A contended lock must stop at its deadline before migration state is read."""
    connection = _MigrationConnection(lock_results=[False, False, False, False])
    ticks = iter([0.0, 0.0, 0.4, 0.8, 1.0])
    sleeps: list[float] = []

    with pytest.raises(migrations.MigrationLockTimeoutError, match="scope users"):
        migrations._acquire_migration_lock(
            connection,
            "users",
            timeout_seconds=1.0,
            poll_interval_seconds=0.4,
            monotonic=lambda: next(ticks),
            sleep=sleeps.append,
        )

    assert sleeps == pytest.approx([0.4, 0.4, 0.2])
    assert all("pg_try_advisory_xact_lock" in sql for sql, _ in connection.calls)


def test_apply_migrations_rejects_checksum_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An edited historical migration must fail before executing its SQL."""
    migration = _write_migration(tmp_path, "001_users.sql")
    monkeypatch.setattr(migrations, "_MIGRATIONS_ROOT", tmp_path)
    connection = _MigrationConnection(checksum="recorded-old-checksum")

    with pytest.raises(migrations.MigrationChecksumError, match=migration.name):
        migrations.apply_migrations(connection, "users")

    assert migration.read_text(encoding="utf-8").strip() not in [
        sql for sql, _ in connection.calls
    ]


def test_verify_migrations_detects_partial_schema_without_ddl(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Runtime readiness must reject a missing required table using reads only."""
    monkeypatch.setattr(migrations, "_MIGRATIONS_ROOT", tmp_path)
    connection = _ReadinessConnection(missing_table="subscriptions")

    with pytest.raises(migrations.DatabaseNotReadyError, match="subscriptions"):
        migrations.verify_migrations(
            connection,
            "users",
            required_tables=("user_weights", "subscriptions"),
        )

    assert all(not statement.startswith(("CREATE", "ALTER", "INSERT")) for statement in connection.statements)


def test_verify_migrations_accepts_complete_checksum_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Runtime readiness accepts every expected migration with its exact checksum."""
    migration = _write_migration(tmp_path, "001_users.sql")
    monkeypatch.setattr(migrations, "_MIGRATIONS_ROOT", tmp_path)
    connection = _ReadinessConnection(
        migration_rows=[(migration.name, migrations._checksum(migration))]
    )

    migrations.verify_migrations(
        connection,
        "users",
        required_tables=("user_weights",),
    )

    assert all(not statement.startswith(("CREATE", "ALTER", "INSERT")) for statement in connection.statements)


def test_market_readiness_guard_is_thread_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Concurrent threads publish one successful database-authoritative check."""
    calls = 0
    calls_lock = threading.Lock()

    def verify() -> None:
        nonlocal calls
        time.sleep(0.01)
        with calls_lock:
            calls += 1

    monkeypatch.setattr(db, "_market_initialized", False)
    monkeypatch.setattr(db, "verify_market_database", verify)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: db._ensure_init(), range(16)))

    assert calls == 1
    assert db._market_initialized is True


def test_failed_readiness_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """A transient database failure must allow a later explicit operation to retry."""
    attempts = 0

    def verify() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("database unavailable")

    monkeypatch.setattr(db, "_users_initialized", False)
    monkeypatch.setattr(db, "verify_users_database", verify)

    with pytest.raises(ConnectionError, match="unavailable"):
        db._ensure_user_init()
    db._ensure_user_init()

    assert attempts == 2
    assert db._users_initialized is True


def test_production_migration_url_fails_closed_on_missing_or_shared_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production release execution must use a secret unavailable to runtime."""
    monkeypatch.setattr(migrate, "is_production", lambda: True)
    monkeypatch.delenv("DATABASE_MIGRATION_MARKET_URL", raising=False)

    with pytest.raises(RuntimeError, match="is required"):
        migrate._migration_url("MARKET", "postgresql://runtime")

    monkeypatch.setenv("DATABASE_MIGRATION_MARKET_URL", "postgresql://runtime")
    with pytest.raises(RuntimeError, match="distinct"):
        migrate._migration_url("MARKET", "postgresql://runtime")

    monkeypatch.setenv(
        "DATABASE_MIGRATION_MARKET_URL",
        "postgresql://shared@database/app?application_name=migration",
    )
    with pytest.raises(RuntimeError, match="distinct"):
        migrate._migration_url("MARKET", "postgresql://shared@database/app")


def test_runtime_rejects_exposed_migration_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A web or worker process must not inherit the release-only secret."""
    monkeypatch.setenv("PROCESS_ROLE", "web")
    monkeypatch.setenv("DATABASE_MIGRATION_MARKET_URL", "postgresql://secret")

    with pytest.raises(RuntimeError, match="must not be available"):
        db.verify_runtime_credential_boundary()

    monkeypatch.setenv("PROCESS_ROLE", "migration")
    db.verify_runtime_credential_boundary()
