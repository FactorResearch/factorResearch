"""Run the dedicated, fail-closed PostgreSQL release migration phase."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from codes.core.config import is_production
from codes.data import analytics_db, db, temporal
from codes.data.migrations import apply_migrations
from codes.services.analysis_snapshot_service import SNAPSHOT_DDL


def main() -> None:
    """Initialize every configured schema with migration-only credentials.

    Production requires distinct migration URLs for market and users databases.
    The release process may receive these secrets; normal web and worker
    processes must receive only their runtime URLs. Local development may fall
    back to runtime URLs so a developer can run the same command explicitly.

    Returns:
        None after all configured schema transactions commit.

    Raises:
        RuntimeError: If production migration credentials are absent or reuse a
            runtime URL, or if the lock timeout is invalid.
        Exception: Propagates database, privilege, lock, SQL, and checksum
            failures so deployment stops before web or workers start.

    Side Effects:
        Connects to configured PostgreSQL databases and executes serialized,
        versioned release DDL. No credential or SQL payload is logged.
    """
    timeout = _lock_timeout_seconds()
    market_runtime_url = db._db_url()
    market_url = _migration_url("MARKET", market_runtime_url)
    users_url = _migration_url("USERS", db._users_db_url())
    db.init_db(
        market_url,
        additional_bootstrap_sql=(temporal.SCHEMA,),
        lock_timeout_seconds=timeout,
    )
    db.init_user_db(users_url, lock_timeout_seconds=timeout)
    runtime_users_role = urlparse(db._users_db_url()).username
    if runtime_users_role:
        db.configure_portfolio_runtime_role(users_url, runtime_users_role)
    elif is_production():
        raise RuntimeError("DATABASE_USERS_URL must identify a PostgreSQL runtime role")

    analytics_runtime_url = _analytics_runtime_url()
    if analytics_runtime_url is not None and analytics_runtime_url != market_runtime_url:
        analytics_url = _migration_url("ANALYTICS", analytics_runtime_url)
    else:
        analytics_url = market_url
    _initialize_analytics_schema(analytics_url, lock_timeout_seconds=timeout)


def _migration_url(scope: str, runtime_url: str) -> str:
    """Resolve one release-only URL and reject unsafe production credential reuse.

    Args:
        scope: Uppercase configuration scope such as ``MARKET``.
        runtime_url: Normal role URL used only as a local-development fallback
            and as the production separation comparison.

    Returns:
        The URL to use for the release migration transaction.

    Raises:
        RuntimeError: If production lacks a dedicated URL or reuses the exact
            runtime credential.
    """
    name = f"DATABASE_MIGRATION_{scope}_URL"
    configured = os.environ.get(name, "").strip()
    if is_production():
        if not configured:
            raise RuntimeError(f"{name} is required for the production migration phase")
        migration_role = urlparse(configured).username
        runtime_role = urlparse(runtime_url).username
        if configured == runtime_url or (
            migration_role is not None and migration_role == runtime_role
        ):
            raise RuntimeError(f"{name} must use credentials distinct from the runtime role")
    return configured or runtime_url


def _analytics_runtime_url() -> str | None:
    """Return configured analytics storage before its final market fallback."""
    return (
        os.environ.get("DATABASE_ANALYTICS_URL")
        or os.environ.get("ANALYTICS_DATABASE_URL")
        or os.environ.get("FACTORRESEARCH_ANALYTICS_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
    )


def _lock_timeout_seconds() -> float:
    """Parse the bounded release lock timeout from centralized deployment input."""
    raw = os.environ.get("DATABASE_MIGRATION_LOCK_TIMEOUT_SECONDS", "30")
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise RuntimeError("DATABASE_MIGRATION_LOCK_TIMEOUT_SECONDS must be numeric") from exc
    if timeout < 0:
        raise RuntimeError("DATABASE_MIGRATION_LOCK_TIMEOUT_SECONDS must be non-negative")
    return timeout


def _initialize_analytics_schema(
    database_url: str,
    *,
    lock_timeout_seconds: float,
) -> None:
    """Initialize analytics events and snapshots in one serialized transaction.

    Args:
        database_url: Dedicated migration-role URL for the owning database.
        lock_timeout_seconds: Maximum seconds to wait for another analytics
            migration transaction.

    Returns:
        None after both analytics schema fragments and tracker state commit.

    Raises:
        Exception: Propagates connection, lock, privilege, SQL, and checksum
            failures so release execution stops.

    Side Effects:
        Opens one direct Psycopg transaction and executes trusted repository DDL.
    """
    import psycopg

    bootstrap_sql = "\n".join((analytics_db.SCHEMA, SNAPSHOT_DDL))
    with psycopg.connect(database_url) as connection:
        apply_migrations(
            connection,
            "analytics",
            bootstrap_sql=bootstrap_sql,
            lock_timeout_seconds=lock_timeout_seconds,
        )


if __name__ == "__main__":
    main()
