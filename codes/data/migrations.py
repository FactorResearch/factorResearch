"""Serialize and verify version-controlled PostgreSQL migrations.

This module owns migration discovery, advisory locking, checksum bookkeeping,
and read-only readiness checks. Database modules own connection lifecycle and
declare their bootstrap SQL and required tables. Runtime request paths must use
``verify_migrations`` and must never call ``apply_migrations``.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol, TypeAlias

_MIGRATIONS_ROOT = Path(__file__).resolve().parents[2] / "migrations"
_LOGGER = logging.getLogger(__name__)
_LOCK_NAMESPACE = "cenvarn:database-migrations:v1"

MigrationRow: TypeAlias = Mapping[str, object] | Sequence[object]


class MigrationQueryResult(Protocol):
    """Describe the bounded query-result surface required by this module."""

    def fetchone(self) -> MigrationRow | None:
        """Return one row or None when the query produced no match."""
        ...

    def fetchall(self) -> Sequence[MigrationRow]:
        """Return all rows from a bounded migration-state query."""
        ...


class MigrationConnection(Protocol):
    """Describe the Psycopg-compatible execution boundary used by migrations."""

    def execute(
        self,
        query: str,
        params: Mapping[str, object] | None = None,
    ) -> MigrationQueryResult:
        """Execute trusted SQL with optional parameterized scalar values."""
        ...


class MigrationError(RuntimeError):
    """Base error for migration state that cannot safely proceed."""


class MigrationLockTimeoutError(MigrationError):
    """Report that another release process held the migration lease too long."""


class MigrationChecksumError(MigrationError):
    """Report that repository SQL differs from its recorded immutable checksum."""


class DatabaseNotReadyError(MigrationError):
    """Report that a runtime database is missing required schema state."""


def apply_migrations(
    connection: MigrationConnection,
    scope: str,
    *,
    bootstrap_sql: str | None = None,
    lock_timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.1,
) -> int:
    """Apply one database scope under a bounded transaction advisory lock.

    The caller owns the outer transaction. Bootstrap DDL, every migration file,
    and every checksum row therefore commit or roll back together. PostgreSQL
    automatically releases the advisory lock when that transaction ends or the
    connection is lost.

    Args:
        connection: Open Psycopg-compatible connection in an active transaction.
        scope: Stable database ownership scope such as ``"market"`` or ``"users"``.
        bootstrap_sql: Optional trusted repository DDL for first-time databases.
        lock_timeout_seconds: Maximum monotonic seconds to wait for another
            migration transaction. Zero performs one immediate attempt.
        poll_interval_seconds: Maximum delay between non-blocking lock attempts.

    Returns:
        The number of versioned migration files applied by this invocation.

    Raises:
        ValueError: If the scope or timeout configuration is invalid.
        MigrationLockTimeoutError: If the advisory lock deadline expires.
        MigrationChecksumError: If an applied file no longer matches its record.
        Exception: Propagates PostgreSQL or filesystem failures so the caller
            rolls the transaction back.

    Side Effects:
        Acquires a database-local advisory transaction lock, may execute trusted
        bootstrap and migration SQL, writes checksum records, and emits
        metadata-only operational logs. It never logs SQL or connection values.
    """
    normalized_scope = _validate_scope(scope)
    started_at = time.monotonic()
    _acquire_migration_lock(
        connection,
        normalized_scope,
        timeout_seconds=lock_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            scope       TEXT NOT NULL,
            migration   TEXT NOT NULL,
            checksum    TEXT NOT NULL,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (scope, migration)
        )
        """
    )
    if bootstrap_sql:
        connection.execute(bootstrap_sql)

    applied_count = 0
    for path in _migration_files(normalized_scope):
        checksum = _checksum(path)
        applied = connection.execute(
            """
            SELECT checksum
            FROM schema_migrations
            WHERE scope = %(scope)s AND migration = %(migration)s
            """,
            {"scope": normalized_scope, "migration": path.name},
        ).fetchone()
        if applied:
            recorded = _row_value(applied, "checksum", 0)
            if recorded != checksum:
                raise MigrationChecksumError(
                    f"Migration checksum changed for scope {normalized_scope}: {path.name}"
                )
            continue
        connection.execute(path.read_text(encoding="utf-8"))
        connection.execute(
            """
            INSERT INTO schema_migrations (scope, migration, checksum)
            VALUES (%(scope)s, %(migration)s, %(checksum)s)
            """,
            {
                "scope": normalized_scope,
                "migration": path.name,
                "checksum": checksum,
            },
        )
        applied_count += 1

    _LOGGER.info(
        "database_migration_complete scope=%s applied=%d elapsed_ms=%d",
        normalized_scope,
        applied_count,
        round((time.monotonic() - started_at) * 1000),
    )
    return applied_count


def verify_migrations(
    connection: MigrationConnection,
    scope: str,
    *,
    required_tables: Sequence[str] = (),
) -> None:
    """Verify that runtime schema is complete without executing data definition SQL.

    Args:
        connection: Open Psycopg-compatible runtime connection.
        scope: Stable database ownership scope to compare with repository files.
        required_tables: Unqualified trusted table names required by the runtime.

    Returns:
        None after every required table, migration row, and checksum is verified.

    Raises:
        ValueError: If the scope or a required table name is invalid.
        DatabaseNotReadyError: If schema tracking, a required table, or an
            expected migration record is missing.
        MigrationChecksumError: If repository SQL differs from recorded state.
        Exception: Propagates database availability or privilege failures.

    Side Effects:
        Reads PostgreSQL catalogs and ``schema_migrations``. It performs no DDL,
        writes, retries, or fallback initialization.
    """
    normalized_scope = _validate_scope(scope)
    tracker = connection.execute(
        "SELECT to_regclass(%(table)s)", {"table": "schema_migrations"}
    ).fetchone()
    if not tracker or _row_value(tracker, "to_regclass", 0) is None:
        raise DatabaseNotReadyError(
            f"Database scope {normalized_scope} is not initialized: schema_migrations is missing"
        )

    for table in required_tables:
        normalized_table = _validate_identifier(table, label="table")
        row = connection.execute(
            "SELECT to_regclass(%(table)s)", {"table": normalized_table}
        ).fetchone()
        if not row or _row_value(row, "to_regclass", 0) is None:
            raise DatabaseNotReadyError(
                f"Database scope {normalized_scope} is not initialized: "
                f"required table {normalized_table} is missing"
            )

    rows = connection.execute(
        """
        SELECT migration, checksum
        FROM schema_migrations
        WHERE scope = %(scope)s
        ORDER BY migration
        """,
        {"scope": normalized_scope},
    ).fetchall()
    recorded = {
        str(_row_value(row, "migration", 0)): str(_row_value(row, "checksum", 1))
        for row in rows
    }
    for path in _migration_files(normalized_scope):
        checksum = recorded.get(path.name)
        if checksum is None:
            raise DatabaseNotReadyError(
                f"Database scope {normalized_scope} is missing migration {path.name}"
            )
        expected = _checksum(path)
        if checksum != expected:
            raise MigrationChecksumError(
                f"Migration checksum changed for scope {normalized_scope}: {path.name}"
            )

    _LOGGER.info(
        "database_readiness_verified scope=%s migrations=%d required_tables=%d",
        normalized_scope,
        len(recorded),
        len(required_tables),
    )


def _acquire_migration_lock(
    connection: MigrationConnection,
    scope: str,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Acquire one database-local transaction lock before inspecting state.

    PostgreSQL advisory keys are evaluated in the current database, so the
    connection supplies the database identity while the stable key supplies the
    migration scope. Non-blocking attempts make the deadline explicit and keep
    lock contention from hanging a deployment indefinitely.

    Args:
        connection: Open connection whose current transaction owns the lock.
        scope: Validated migration scope used to derive the advisory key.
        timeout_seconds: Maximum monotonic seconds allowed for acquisition.
        poll_interval_seconds: Maximum sleep between attempts.
        monotonic: Injectable monotonic clock used by deterministic tests.
        sleep: Injectable bounded sleeper used by deterministic tests.

    Returns:
        None once the transaction owns the lock.

    Raises:
        ValueError: If timeout or poll interval is invalid.
        MigrationLockTimeoutError: If the deadline expires.

    Side Effects:
        Executes non-blocking PostgreSQL advisory-lock queries and may sleep for
        bounded intervals. The lock is released only when the transaction ends.
    """
    if timeout_seconds < 0:
        raise ValueError("lock_timeout_seconds must be non-negative")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")

    deadline = monotonic() + timeout_seconds
    key = _advisory_lock_key(scope)
    while True:
        row = connection.execute(
            "SELECT pg_try_advisory_xact_lock(%(lock_key)s)",
            {"lock_key": key},
        ).fetchone()
        if row and bool(_row_value(row, "pg_try_advisory_xact_lock", 0)):
            _LOGGER.info("database_migration_lock_acquired scope=%s", scope)
            return
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise MigrationLockTimeoutError(
                f"Timed out after {timeout_seconds:g}s waiting for migration scope {scope}"
            )
        sleep(min(poll_interval_seconds, remaining))


def _migration_files(scope: str) -> list[Path]:
    """Return ordered repository migration files for one validated scope."""
    return sorted(_MIGRATIONS_ROOT.glob(f"*_{scope}.sql"))


def _advisory_lock_key(scope: str) -> int:
    """Return a stable signed 64-bit PostgreSQL advisory key for one scope."""
    digest = hashlib.sha256(f"{_LOCK_NAMESPACE}:{scope}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


def _checksum(path: Path) -> str:
    """Return the stable SHA-256 checksum used for migration drift detection."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row_value(row: MigrationRow, key: str, index: int) -> object:
    """Read one value from Psycopg tuple or mapping row contracts."""
    if isinstance(row, Mapping):
        return row[key]
    return row[index]


def _validate_scope(scope: str) -> str:
    """Return a normalized SQL-independent scope or reject unsafe ambiguity."""
    return _validate_identifier(scope, label="scope")


def _validate_identifier(value: str, *, label: str) -> str:
    """Validate trusted repository identifiers used in messages and file matching."""
    normalized = value.strip().lower() if isinstance(value, str) else ""
    if not normalized or not normalized.replace("_", "").isalnum():
        raise ValueError(f"Migration {label} must contain only letters, numbers, and underscores")
    return normalized
