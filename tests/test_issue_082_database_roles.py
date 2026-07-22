"""Security contracts for ISSUE_082 PostgreSQL workload separation."""

from __future__ import annotations

from pathlib import Path

import pytest

from codes.core.database_roles import DatabaseWorkload, verify_database_role
from codes.data import db


class _Result:
    """Return one configured catalog row to role verification."""

    def __init__(self, row: object) -> None:
        self._row = row

    def fetchone(self) -> object:
        """Return the immutable row configured by the test."""

        return self._row


class _Connection:
    """Capture the bounded role catalog query without a real database."""

    def __init__(self, row: object) -> None:
        self.row = row
        self.calls: list[tuple[str, object]] = []

    def execute(self, statement: str, params: object = None) -> _Result:
        """Record one query and return the configured role row."""

        self.calls.append((statement, params))
        return _Result(self.row)


def _safe_row(workload: DatabaseWorkload) -> list[bool]:
    """Build the exact safe catalog projection for one canonical workload."""

    memberships = [candidate is workload for candidate in DatabaseWorkload]
    is_migration = workload is DatabaseWorkload.MIGRATION
    return [
        False,
        False,
        False,
        False,
        False,
        True,
        is_migration,
        is_migration,
        *memberships,
    ]


@pytest.mark.parametrize("workload", list(DatabaseWorkload))
def test_each_canonical_role_profile_accepts_only_its_safe_authority(
    workload: DatabaseWorkload,
) -> None:
    """Blue/green login names are irrelevant when membership is exact and safe."""

    connection = _Connection(_safe_row(workload))

    verify_database_role(connection, workload)

    assert connection.calls[0][1] == {"expected_role": workload.value}


@pytest.mark.parametrize("unsafe_index", range(5))
def test_runtime_role_rejects_every_dangerous_postgresql_attribute(
    unsafe_index: int,
) -> None:
    """No canonical workload may carry cluster-level escape authority."""

    row = _safe_row(DatabaseWorkload.APP)
    row[unsafe_index] = True

    with pytest.raises(RuntimeError, match="is forbidden"):
        verify_database_role(_Connection(row), DatabaseWorkload.APP)


def test_runtime_role_rejects_wrong_or_overlapping_membership_and_ownership() -> None:
    """A credential cannot combine app, service, migration, or worker authority."""

    missing = _safe_row(DatabaseWorkload.APP)
    missing[5] = False
    with pytest.raises(RuntimeError, match="membership is missing"):
        verify_database_role(_Connection(missing), DatabaseWorkload.APP)

    overlapping = _safe_row(DatabaseWorkload.APP)
    overlapping[9] = True
    with pytest.raises(RuntimeError, match="memberships overlap"):
        verify_database_role(_Connection(overlapping), DatabaseWorkload.APP)

    owner = _safe_row(DatabaseWorkload.APP)
    owner[7] = True
    with pytest.raises(RuntimeError, match="ownership is forbidden"):
        verify_database_role(_Connection(owner), DatabaseWorkload.APP)


def test_market_worker_url_is_required_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Market workers never fall back to the web application's market login."""

    monkeypatch.setenv("PROCESS_ROLE", "sec-worker")
    monkeypatch.setenv("DATABASE_MARKET_URL", "postgresql://app@market/database")
    monkeypatch.delenv("DATABASE_MARKET_WORKER_URL", raising=False)
    monkeypatch.setattr(db, "is_production", lambda: True)

    with pytest.raises(RuntimeError, match="DATABASE_MARKET_WORKER_URL is required"):
        db._db_url()

    monkeypatch.setenv(
        "DATABASE_MARKET_WORKER_URL",
        "postgresql://worker@market/database",
    )
    assert db._db_url() == "postgresql://worker@market/database"


def test_market_worker_rejects_users_and_migration_secret_exposure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A market-only process fails before it can reach tenant databases."""

    monkeypatch.setattr(db, "is_production", lambda: True)
    monkeypatch.setenv("PROCESS_ROLE", "market-worker")
    monkeypatch.setenv("DATABASE_USERS_URL", "postgresql://app@users/database")

    with pytest.raises(RuntimeError, match="must not be available to market workers"):
        db.verify_runtime_credential_boundary()


def test_provisioning_and_migrations_encode_the_complete_role_contract() -> None:
    """Versioned SQL must preserve role flags, revocations, grants, and policies."""

    cluster = Path("deploy/postgresql/001_canonical_roles.sql").read_text(encoding="utf-8")
    users_access = Path("deploy/postgresql/002_users_database_access.sql").read_text(
        encoding="utf-8"
    )
    market_access = Path("deploy/postgresql/003_market_database_access.sql").read_text(
        encoding="utf-8"
    )
    analytics_access = Path("deploy/postgresql/004_analytics_database_access.sql").read_text(
        encoding="utf-8"
    )
    users = Path("migrations/005_issue_082_least_privilege_users.sql").read_text(encoding="utf-8")
    market = Path("migrations/001_issue_082_least_privilege_market.sql").read_text(encoding="utf-8")
    analytics = Path("migrations/001_issue_082_least_privilege_analytics.sql").read_text(
        encoding="utf-8"
    )

    for role in DatabaseWorkload:
        assert role.value in cluster
    assert "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE" in cluster
    assert "NOREPLICATION NOBYPASSRLS" in cluster
    assert "REVOKE CONNECT, TEMPORARY" in users_access
    assert "REVOKE CONNECT, TEMPORARY" in market_access
    assert "REVOKE CONNECT, TEMPORARY" in analytics_access
    assert "REVOKE CONNECT" in users_access and "cenvarn_market_worker" in users_access
    assert "REVOKE CONNECT" in market_access and "cenvarn_service" in market_access
    assert "FROM PUBLIC" in users and "FROM PUBLIC" in market
    assert "FROM PUBLIC" in analytics
    assert "TO cenvarn_service" in users
    assert "USING (true) WITH CHECK (true)" in users
    for table_name, _owner_column in db._USER_OWNED_TABLES:
        assert f"('{table_name}')" in users
