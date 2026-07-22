"""Validate canonical PostgreSQL workload identities at process boundaries.

This module owns the role-membership and dangerous-attribute contract shared by
runtime readiness and release migrations. It depends only on a narrow execution
protocol so infrastructure code can pass Psycopg connections without leaking the
driver into application configuration or tests. It never provisions roles,
reads tenant rows, or logs login names and credentials.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import Mapping, Protocol


class DatabaseRoleResult(Protocol):
    """Expose the single-row result required by role verification."""

    def fetchone(self) -> object:
        """Return the connected role's bounded catalog projection."""

        ...


class DatabaseRoleConnection(Protocol):
    """Describe the PostgreSQL catalog execution boundary used by readiness."""

    def execute(
        self,
        statement: str,
        params: Mapping[str, object] | None = None,
    ) -> DatabaseRoleResult:
        """Execute one parameterized catalog query and return its result."""

        ...


class DatabaseWorkload(str, Enum):
    """Name each canonical PostgreSQL authorization profile.

    Values identify operational workloads rather than environment-specific
    LOGIN principals. Production credentials may rotate between blue and green
    logins, but each login must be a member of exactly one canonical NOLOGIN
    role represented here.
    """

    APP = "cenvarn_app"
    SERVICE = "cenvarn_service"
    MIGRATION = "cenvarn_migration"
    MARKET_WORKER = "cenvarn_market_worker"
    READONLY = "cenvarn_readonly"


MARKET_WORKER_PROCESS_ROLES = frozenset(
    {"analysis-worker", "canada-ingest-worker", "market-worker", "sec-worker"}
)


def is_market_worker_process(process_role: str | None) -> bool:
    """Return whether a process must use the market-worker database identity.

    Args:
        process_role: Optional deployment process label. Matching is
            case-insensitive and ignores surrounding whitespace.

    Returns:
        True for the bounded set of market ingestion and analysis workers;
        otherwise False.
    """

    return str(process_role or "").strip().lower() in MARKET_WORKER_PROCESS_ROLES


def verify_database_role(
    connection: DatabaseRoleConnection,
    workload: DatabaseWorkload,
) -> None:
    """Fail unless the connected identity matches one safe workload profile.

    The check rejects PostgreSQL authority that could escape repository grants:
    superuser, role/database creation, replication, RLS bypass, unexpected
    canonical memberships, schema creation, or object ownership. Only the
    migration workload may create or own objects.

    Args:
        connection: Open connection authenticated with the credential under
            inspection. The caller owns its transaction and lifecycle.
        workload: Canonical authorization profile required by the caller.

    Returns:
        None when all bounded catalog invariants pass.

    Raises:
        RuntimeError: If the role is absent, unsafe, assigned to the wrong
            workload, or has incompatible schema/object authority.
        Exception: Propagates catalog access failures so startup fails closed.

    Side Effects:
        Performs one bounded PostgreSQL catalog read. It never reads user rows
        or includes the environment-specific login name in an error.
    """

    row = connection.execute(
        """
        SELECT
            role.rolsuper,
            role.rolcreaterole,
            role.rolcreatedb,
            role.rolreplication,
            role.rolbypassrls,
            pg_has_role(current_user, %(expected_role)s, 'MEMBER') AS expected_member,
            has_schema_privilege(current_user, 'public', 'CREATE') AS can_create,
            (
                EXISTS (
                    SELECT 1
                    FROM pg_namespace
                    WHERE nspname = 'public'
                      AND pg_has_role(current_user, nspowner, 'USAGE')
                )
                OR EXISTS (
                    SELECT 1
                    FROM pg_class
                    WHERE relnamespace = 'public'::regnamespace
                      AND pg_has_role(current_user, relowner, 'USAGE')
                )
            ) AS owns_objects,
            pg_has_role(current_user, 'cenvarn_app', 'MEMBER') AS app_member,
            pg_has_role(current_user, 'cenvarn_service', 'MEMBER') AS service_member,
            pg_has_role(current_user, 'cenvarn_migration', 'MEMBER') AS migration_member,
            pg_has_role(current_user, 'cenvarn_market_worker', 'MEMBER') AS market_worker_member,
            pg_has_role(current_user, 'cenvarn_readonly', 'MEMBER') AS readonly_member
        FROM pg_roles AS role
        WHERE role.rolname = current_user
        """,
        {"expected_role": workload.value},
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Unsafe PostgreSQL role for {workload.value}: role is unavailable")

    values = _role_values(row)
    dangerous = (
        "superuser",
        "role creation",
        "database creation",
        "replication",
        "RLS bypass",
    )
    for label, enabled in zip(dangerous, values[:5], strict=True):
        if enabled:
            raise RuntimeError(f"Unsafe PostgreSQL role for {workload.value}: {label} is forbidden")
    if not values[5]:
        raise RuntimeError(
            f"Unsafe PostgreSQL role for {workload.value}: canonical membership is missing"
        )

    is_migration = workload is DatabaseWorkload.MIGRATION
    if values[6] is not is_migration:
        expectation = "required" if is_migration else "forbidden"
        raise RuntimeError(
            f"Unsafe PostgreSQL role for {workload.value}: schema creation is {expectation}"
        )
    if values[7] is not is_migration:
        expectation = "required" if is_migration else "forbidden"
        raise RuntimeError(
            f"Unsafe PostgreSQL role for {workload.value}: object ownership is {expectation}"
        )

    memberships = values[8:13]
    expected_index = list(DatabaseWorkload).index(workload)
    if any(enabled != (index == expected_index) for index, enabled in enumerate(memberships)):
        raise RuntimeError(
            f"Unsafe PostgreSQL role for {workload.value}: canonical memberships overlap"
        )


def _role_values(row: object) -> tuple[bool, ...]:
    """Normalize tuple or mapping catalog rows into the fixed boolean contract.

    Args:
        row: Psycopg tuple/mapping row returned by the role verification query.

    Returns:
        Thirteen booleans ordered exactly as the query projection.

    Raises:
        RuntimeError: If the row does not expose the complete safe contract.
    """

    if isinstance(row, Mapping):
        keys = (
            "rolsuper",
            "rolcreaterole",
            "rolcreatedb",
            "rolreplication",
            "rolbypassrls",
            "expected_member",
            "can_create",
            "owns_objects",
            "app_member",
            "service_member",
            "migration_member",
            "market_worker_member",
            "readonly_member",
        )
        try:
            return tuple(bool(row[key]) for key in keys)
        except KeyError as exc:
            raise RuntimeError("PostgreSQL role verification returned an incomplete row") from exc
    if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
        raise RuntimeError("PostgreSQL role verification returned an invalid row")
    values = tuple(bool(value) for value in row)
    if len(values) != 13:
        raise RuntimeError("PostgreSQL role verification returned an incomplete row")
    return values
