"""Apply ordered, version-controlled PostgreSQL migrations.

This module owns only migration discovery and bookkeeping.  The database module
owns connection lifecycle and base schema creation; individual SQL files own
their data-preserving rollout and rollback notes.
"""

from __future__ import annotations

from pathlib import Path

_MIGRATIONS_ROOT = Path(__file__).resolve().parents[2] / "migrations"


def apply_migrations(connection: object, scope: str) -> None:
    """Apply unapplied migrations for one database scope.

    Args:
        connection: An open psycopg connection whose transaction is managed by
            the caller.
        scope: Database ownership scope, such as ``"users"``.

    Raises:
        RuntimeError: If a migration has already been recorded with a
            different checksum.

    Side Effects:
        Executes trusted repository SQL and records applied filenames and
        checksums in the scoped database.  Re-running is idempotent.
    """
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
    migration_files = sorted(_MIGRATIONS_ROOT.glob(f"*_{scope}.sql"))
    for path in migration_files:
        checksum = _checksum(path)
        applied = connection.execute(
            "SELECT checksum FROM schema_migrations WHERE scope = %(scope)s AND migration = %(migration)s",
            {"scope": scope, "migration": path.name},
        ).fetchone()
        if applied:
            recorded = applied[0] if not isinstance(applied, dict) else applied["checksum"]
            if recorded != checksum:
                raise RuntimeError(f"Migration checksum changed: {path.name}")
            continue
        connection.execute(path.read_text(encoding="utf-8"))
        connection.execute(
            """
            INSERT INTO schema_migrations (scope, migration, checksum)
            VALUES (%(scope)s, %(migration)s, %(checksum)s)
            """,
            {"scope": scope, "migration": path.name, "checksum": checksum},
        )


def _checksum(path: Path) -> str:
    """Return the stable SHA-256 checksum used for migration drift detection."""
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
