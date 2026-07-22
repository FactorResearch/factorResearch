"""Tenant-scoped PostgreSQL authority for portfolios and simulations."""
# mypy: disable-error-code=type-arg

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import uuid
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, Iterator, Protocol, cast

from psycopg.rows import dict_row

from codes.core.config import is_production

from . import db

SIMULATION_MODEL_VERSION = "portfolio-simulation-v1"
SIMULATION_TTL_SECONDS = 24 * 60 * 60


class _Connection(Protocol):
    row_factory: Any

    def execute(self, statement: str, params: dict[str, Any] | None = None) -> Any: ...


def is_enabled() -> bool:
    """Return whether runtime persistence must use PostgreSQL.

    Local cache persistence remains available only as a test/development
    compatibility adapter while legacy records are imported. Production can
    never opt back into file authority.
    """
    configured = os.environ.get("PORTFOLIO_STORAGE_BACKEND", "").strip().lower()
    if is_production():
        if configured == "cache":
            raise RuntimeError("Production portfolio storage cannot use local cache files")
        return True
    # Development keeps the compatibility adapter unless PostgreSQL is chosen
    # explicitly. This prevents a developer's stale .env URL from silently
    # redirecting unit tests or one-off local scripts to a real database.
    return configured == "postgres"


def _owner(user_id: str) -> str:
    owner = str(user_id or "").strip()
    if not owner:
        raise ValueError("Authenticated user id is required for portfolio storage")
    return owner


@contextmanager
def _tenant_connection(user_id: str) -> Iterator[_Connection]:
    owner = _owner(user_id)
    db._ensure_user_init()
    with db._users_conn() as connection:
        connection.row_factory = dict_row
        connection.execute(
            "SELECT set_config('app.user_id', %(user_id)s, true)",
            {"user_id": owner},
        )
        yield cast(_Connection, connection)


def _json_default(value: object) -> object:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    item = getattr(value, "item", None)
    try:
        scalar = item() if callable(item) else None  # numpy scalar
    except ValueError:
        scalar = None
    if scalar is not None:
        return None if isinstance(scalar, float) and not math.isfinite(scalar) else scalar
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable")


def _as_json(value: object) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True, allow_nan=False)


def _portfolio_record(connection: _Connection, row: dict) -> dict:
    holdings = connection.execute(
        """
        SELECT symbol, security_id::text, shares, price_at_add, company_name, added_date
        FROM portfolio_holdings
        WHERE portfolio_id = %(portfolio_id)s
        ORDER BY symbol
        """,
        {"portfolio_id": row["portfolio_id"]},
    ).fetchall()
    return {
        "id": str(row["portfolio_id"]).replace("-", ""),
        "name": row["name"],
        "created": row["created_at"].isoformat(),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "deleted_at": row["deleted_at"].isoformat() if row.get("deleted_at") else None,
        "version": int(row["version"]),
        "holdings": {
            holding["symbol"]: {
                "security_id": holding.get("security_id"),
                "shares": float(holding["shares"]),
                "price_at_add": float(holding["price_at_add"]),
                "name": holding["company_name"],
                "added_date": holding["added_date"].isoformat(),
            }
            for holding in holdings
        },
    }


def list_portfolios(user_id: str) -> list[str]:
    with _tenant_connection(user_id) as connection:
        rows = connection.execute(
            "SELECT name FROM portfolios WHERE deleted_at IS NULL ORDER BY name"
        ).fetchall()
    return [str(row["name"]) for row in rows]


def load_portfolio(user_id: str, name: str) -> dict | None:
    with _tenant_connection(user_id) as connection:
        row = connection.execute(
            """
            SELECT portfolio_id, name, version, created_at, updated_at, deleted_at
            FROM portfolios
            WHERE name = %(name)s AND deleted_at IS NULL
            """,
            {"name": name},
        ).fetchone()
        return _portfolio_record(connection, row) if row else None


def load_portfolio_by_id(
    user_id: str, portfolio_id: str, *, include_deleted: bool = False
) -> dict | None:
    deleted_clause = "" if include_deleted else "AND deleted_at IS NULL"
    with _tenant_connection(user_id) as connection:
        row = connection.execute(
            f"""SELECT portfolio_id, name, version, created_at, updated_at, deleted_at
                FROM portfolios WHERE portfolio_id = %(portfolio_id)s {deleted_clause}""",  # nosec B608
            {"portfolio_id": portfolio_id},
        ).fetchone()
        return _portfolio_record(connection, row) if row else None


def _holding_payload(raw: dict) -> dict:
    return {
        "security_id": raw.get("security_id") or None,
        "shares": raw["shares"],
        "price_at_add": raw.get("price_at_add") or 0,
        "company_name": str(raw.get("name") or ""),
        "added_date": raw.get("added_date") or dt.date.today().isoformat(),
    }


def _holding_operations(
    holdings: dict[str, dict], prior_holdings: dict[str, dict], *, created: bool
) -> list[tuple[str, str | None, dict | None]]:
    operations: list[tuple[str, str | None, dict | None]] = []
    if created:
        operations.append(("create", None, None))
    for symbol, holding in holdings.items():
        prior = prior_holdings.get(symbol)
        changed = (
            prior is None
            or float(prior["shares"]) != float(holding["shares"])
            or float(prior["price_at_add"]) != float(holding["price_at_add"])
        )
        if changed:
            operations.append(("add" if prior is None else "update", symbol, holding))
    operations.extend(
        ("remove", symbol, prior)
        for symbol, prior in prior_holdings.items()
        if symbol not in holdings
    )
    return operations


def save_portfolio(user_id: str, portfolio: dict, *, expected_version: int | None = None) -> dict:
    owner = _owner(user_id)
    portfolio_id = portfolio.setdefault("id", uuid.uuid4().hex)
    expected = int(portfolio.get("version") or 0) if expected_version is None else expected_version
    name = str(portfolio["name"]).strip()
    if not name:
        raise ValueError("Portfolio name is required")
    holdings = {
        str(symbol).upper(): _holding_payload(value)
        for symbol, value in portfolio.get("holdings", {}).items()
    }

    with _tenant_connection(owner) as connection:
        current = connection.execute(
            """
            SELECT portfolio_id, name, version, created_at, updated_at, deleted_at
            FROM portfolios WHERE portfolio_id = %(portfolio_id)s FOR UPDATE
            """,
            {"portfolio_id": portfolio_id},
        ).fetchone()
        prior_holdings = {}
        if current:
            if int(current["version"]) != expected:
                raise RuntimeError("Portfolio version conflict; reload before retrying.")
            prior_holdings = {
                row["symbol"]: row
                for row in connection.execute(
                    "SELECT symbol, shares, price_at_add FROM portfolio_holdings WHERE portfolio_id = %(portfolio_id)s",
                    {"portfolio_id": portfolio_id},
                ).fetchall()
            }
            next_version = expected + 1
            row = connection.execute(
                """
                UPDATE portfolios
                SET name = %(name)s, version = %(next_version)s, updated_at = NOW(),
                    deleted_at = %(deleted_at)s
                WHERE portfolio_id = %(portfolio_id)s AND version = %(expected)s
                RETURNING portfolio_id, name, version, created_at, updated_at, deleted_at
                """,
                {
                    "name": name,
                    "next_version": next_version,
                    "deleted_at": portfolio.get("deleted_at"),
                    "portfolio_id": portfolio_id,
                    "expected": expected,
                },
            ).fetchone()
            if row is None:
                raise RuntimeError("Portfolio version conflict; reload before retrying.")
        else:
            if expected != 0:
                raise RuntimeError("Portfolio version conflict; record no longer exists.")
            next_version = 1
            row = connection.execute(
                """
                INSERT INTO portfolios (portfolio_id, owner_id, name, version, created_at, updated_at, deleted_at)
                VALUES (%(portfolio_id)s, %(owner_id)s, %(name)s, 1,
                        COALESCE(%(created_at)s::timestamptz, NOW()), NOW(), %(deleted_at)s)
                RETURNING portfolio_id, name, version, created_at, updated_at, deleted_at
                """,
                {
                    "portfolio_id": portfolio_id,
                    "owner_id": owner,
                    "name": name,
                    "created_at": portfolio.get("created_at") or portfolio.get("created"),
                    "deleted_at": portfolio.get("deleted_at"),
                },
            ).fetchone()

        connection.execute(
            "DELETE FROM portfolio_holdings WHERE portfolio_id = %(portfolio_id)s",
            {"portfolio_id": portfolio_id},
        )
        for symbol, holding in holdings.items():
            connection.execute(
                """
                INSERT INTO portfolio_holdings
                    (portfolio_id, owner_id, symbol, security_id, shares, price_at_add,
                     company_name, added_date, updated_at)
                VALUES (%(portfolio_id)s, %(owner_id)s, %(symbol)s, %(security_id)s,
                        %(shares)s, %(price_at_add)s, %(company_name)s, %(added_date)s, NOW())
                """,
                {"portfolio_id": portfolio_id, "owner_id": owner, "symbol": symbol, **holding},
            )

        operations = _holding_operations(holdings, prior_holdings, created=current is None)
        for operation, event_symbol, event_holding in operations:
            connection.execute(
                """
                INSERT INTO portfolio_transactions
                    (transaction_id, portfolio_id, owner_id, portfolio_version, operation,
                     symbol, shares, price, metadata_json)
                VALUES (%(transaction_id)s, %(portfolio_id)s, %(owner_id)s, %(version)s,
                        %(operation)s, %(symbol)s, %(shares)s, %(price)s, %(metadata)s::jsonb)
                """,
                {
                    "transaction_id": str(uuid.uuid4()),
                    "portfolio_id": portfolio_id,
                    "owner_id": owner,
                    "version": next_version,
                    "operation": operation,
                    "symbol": event_symbol,
                    "shares": event_holding.get("shares") if event_holding else None,
                    "price": (event_holding.get("price_at_add") if event_holding else None),
                    "metadata": _as_json({"source": "portfolio-service"}),
                },
            )
        saved = _portfolio_record(connection, row)
    portfolio.clear()
    portfolio.update(saved)
    return portfolio


def delete_portfolio(user_id: str, name: str, *, hard: bool = False) -> None:
    owner = _owner(user_id)
    with _tenant_connection(owner) as connection:
        row = connection.execute(
            "SELECT portfolio_id, version FROM portfolios WHERE name = %(name)s FOR UPDATE",
            {"name": name},
        ).fetchone()
        if not row:
            return
        portfolio_id = row["portfolio_id"]
        if hard:
            connection.execute(
                "DELETE FROM portfolio_tombstones WHERE portfolio_id = %(portfolio_id)s",
                {"portfolio_id": portfolio_id},
            )
            connection.execute(
                "DELETE FROM portfolios WHERE portfolio_id = %(portfolio_id)s",
                {"portfolio_id": portfolio_id},
            )
            return
        next_version = int(row["version"]) + 1
        deleted = connection.execute(
            """
            UPDATE portfolios SET deleted_at = NOW(), updated_at = NOW(), version = %(version)s
            WHERE portfolio_id = %(portfolio_id)s AND deleted_at IS NULL
            RETURNING deleted_at
            """,
            {"version": next_version, "portfolio_id": portfolio_id},
        ).fetchone()
        if not deleted:
            return
        connection.execute(
            """
            INSERT INTO portfolio_tombstones (portfolio_id, owner_id, name, version, deleted_at)
            VALUES (%(portfolio_id)s, %(owner_id)s, %(name)s, %(version)s, %(deleted_at)s)
            ON CONFLICT (portfolio_id) DO UPDATE SET
                version = EXCLUDED.version, deleted_at = EXCLUDED.deleted_at
            """,
            {
                "portfolio_id": portfolio_id,
                "owner_id": owner,
                "name": name,
                "version": next_version,
                "deleted_at": deleted["deleted_at"],
            },
        )
        connection.execute(
            """
            INSERT INTO portfolio_transactions
                (transaction_id, portfolio_id, owner_id, portfolio_version, operation)
            VALUES (%(transaction_id)s, %(portfolio_id)s, %(owner_id)s, %(version)s, 'delete')
            """,
            {
                "transaction_id": str(uuid.uuid4()),
                "portfolio_id": portfolio_id,
                "owner_id": owner,
                "version": next_version,
            },
        )


def list_portfolio_changes(user_id: str, since: str | None = None) -> list[dict]:
    with _tenant_connection(user_id) as connection:
        rows = connection.execute(
            """
            SELECT portfolio_id, name, version, created_at, updated_at, deleted_at
            FROM portfolios
            WHERE (%(since)s::timestamptz IS NULL OR updated_at > %(since)s::timestamptz)
            ORDER BY updated_at, portfolio_id
            """,
            {"since": since},
        ).fetchall()
        return [_portfolio_record(connection, row) for row in rows]


def restore_portfolio(user_id: str, portfolio_id: str, *, expected_version: int) -> dict:
    owner = _owner(user_id)
    with _tenant_connection(owner) as connection:
        row = connection.execute(
            """
            UPDATE portfolios SET deleted_at = NULL, updated_at = NOW(), version = version + 1
            WHERE portfolio_id = %(portfolio_id)s AND version = %(expected)s AND deleted_at IS NOT NULL
            RETURNING portfolio_id, name, version, created_at, updated_at, deleted_at
            """,
            {"portfolio_id": portfolio_id, "expected": expected_version},
        ).fetchone()
        if not row:
            raise ValueError("Deleted portfolio not found or version conflict.")
        connection.execute(
            "DELETE FROM portfolio_tombstones WHERE portfolio_id = %(portfolio_id)s",
            {"portfolio_id": portfolio_id},
        )
        connection.execute(
            """
            INSERT INTO portfolio_transactions
                (transaction_id, portfolio_id, owner_id, portfolio_version, operation)
            VALUES (%(transaction_id)s, %(portfolio_id)s, %(owner_id)s, %(version)s, 'restore')
            """,
            {
                "transaction_id": str(uuid.uuid4()),
                "portfolio_id": portfolio_id,
                "owner_id": owner,
                "version": row["version"],
            },
        )
        return _portfolio_record(connection, row)


def simulation_checksum(portfolio: dict) -> str:
    payload = {
        "portfolio_id": portfolio["id"],
        "version": portfolio["version"],
        "holdings": portfolio.get("holdings", {}),
    }
    return hashlib.sha256(_as_json(payload).encode()).hexdigest()


def load_simulation(user_id: str, portfolio: dict) -> dict | None:
    checksum = simulation_checksum(portfolio)
    with _tenant_connection(user_id) as connection:
        row = connection.execute(
            """
            SELECT result_json FROM portfolio_simulation_results
            WHERE portfolio_id = %(portfolio_id)s AND portfolio_version = %(version)s
              AND model_version = %(model_version)s AND input_checksum = %(checksum)s
              AND deleted_at IS NULL AND expires_at > NOW()
            """,
            {
                "portfolio_id": portfolio["id"],
                "version": portfolio["version"],
                "model_version": SIMULATION_MODEL_VERSION,
                "checksum": checksum,
            },
        ).fetchone()
    return dict(row["result_json"]) if row else None


def save_simulation(user_id: str, portfolio: dict, result: dict) -> None:
    owner = _owner(user_id)
    checksum = simulation_checksum(portfolio)
    with _tenant_connection(owner) as connection:
        connection.execute(
            """
            INSERT INTO portfolio_simulation_results
                (simulation_id, portfolio_id, owner_id, portfolio_version, model_version,
                 input_checksum, result_json, expires_at)
            VALUES (%(simulation_id)s, %(portfolio_id)s, %(owner_id)s, %(version)s,
                    %(model_version)s, %(checksum)s, %(result)s::jsonb,
                    NOW() + (%(ttl)s * INTERVAL '1 second'))
            ON CONFLICT (portfolio_id, portfolio_version, model_version, input_checksum)
            DO UPDATE SET result_json = EXCLUDED.result_json, created_at = NOW(),
                          expires_at = EXCLUDED.expires_at, deleted_at = NULL
            """,
            {
                "simulation_id": str(uuid.uuid4()),
                "portfolio_id": portfolio["id"],
                "owner_id": owner,
                "version": portfolio["version"],
                "model_version": SIMULATION_MODEL_VERSION,
                "checksum": checksum,
                "result": _as_json(result),
                "ttl": SIMULATION_TTL_SECONDS,
            },
        )


def invalidate_simulations(user_id: str, portfolio_name: str) -> None:
    with _tenant_connection(user_id) as connection:
        connection.execute(
            """
            UPDATE portfolio_simulation_results SET deleted_at = NOW()
            WHERE portfolio_id IN (SELECT portfolio_id FROM portfolios WHERE name = %(name)s)
              AND deleted_at IS NULL
            """,
            {"name": portfolio_name},
        )


def erase_user(user_id: str) -> dict[str, int]:
    """Discover and erase active, deleted, simulation, audit, and import rows."""
    counts: dict[str, int] = {}
    with _tenant_connection(user_id) as connection:
        for table in (
            "portfolio_simulation_results",
            "portfolio_transactions",
            "portfolio_holdings",
            "portfolio_tombstones",
            "portfolio_legacy_imports",
            "portfolios",
        ):
            counts[table] = connection.execute(
                f"DELETE FROM {table} WHERE owner_id = %(user_id)s",  # nosec B608
                {"user_id": user_id},
            ).rowcount
    return counts


def export_user_data(user_id: str) -> dict[str, list[dict]]:
    """Export active, deleted, derived, audit, and migration-state records."""
    with _tenant_connection(user_id) as connection:
        portfolio_rows = connection.execute(
            """
            SELECT portfolio_id, name, version, created_at, updated_at, deleted_at
            FROM portfolios ORDER BY created_at, portfolio_id
            """
        ).fetchall()
        portfolios = [_portfolio_record(connection, row) for row in portfolio_rows]
        transactions = connection.execute(
            """
            SELECT transaction_id::text, portfolio_id::text, portfolio_version,
                   operation, symbol, shares, price, occurred_at, metadata_json
            FROM portfolio_transactions ORDER BY occurred_at, transaction_id
            """
        ).fetchall()
        tombstones = connection.execute(
            """
            SELECT portfolio_id::text, name, version, deleted_at, metadata_json
            FROM portfolio_tombstones ORDER BY deleted_at, portfolio_id
            """
        ).fetchall()
        simulations = connection.execute(
            """
            SELECT simulation_id::text, portfolio_id::text, portfolio_version,
                   model_version, input_checksum, result_json, created_at,
                   expires_at, deleted_at
            FROM portfolio_simulation_results ORDER BY created_at, simulation_id
            """
        ).fetchall()
        legacy_imports = connection.execute(
            """
            SELECT source_key, source_checksum, portfolio_id::text, status,
                   error_code, started_at, completed_at
            FROM portfolio_legacy_imports ORDER BY started_at, source_key
            """
        ).fetchall()
    exported = {
        "portfolios": portfolios,
        "transactions": [dict(row) for row in transactions],
        "tombstones": [dict(row) for row in tombstones],
        "simulations": [dict(row) for row in simulations],
        "legacy_imports": [dict(row) for row in legacy_imports],
    }
    return cast(dict[str, list[dict[str, Any]]], json.loads(_as_json(exported)))


def record_legacy_import(
    user_id: str,
    source_key: str,
    checksum: str,
    *,
    status: str,
    portfolio_id: str | None = None,
    error_code: str | None = None,
) -> None:
    with _tenant_connection(user_id) as connection:
        connection.execute(
            """
            INSERT INTO portfolio_legacy_imports
                (owner_id, source_key, source_checksum, portfolio_id, status,
                 error_code, completed_at)
            VALUES (%(owner_id)s, %(source_key)s, %(checksum)s, %(portfolio_id)s,
                    %(status)s, %(error_code)s,
                    CASE WHEN %(status)s = 'processing' THEN NULL ELSE NOW() END)
            ON CONFLICT (owner_id, source_key) DO UPDATE SET
                source_checksum = EXCLUDED.source_checksum,
                portfolio_id = EXCLUDED.portfolio_id,
                status = EXCLUDED.status,
                error_code = EXCLUDED.error_code,
                completed_at = EXCLUDED.completed_at
            """,
            {
                "owner_id": user_id,
                "source_key": source_key,
                "checksum": checksum,
                "portfolio_id": portfolio_id,
                "status": status,
                "error_code": error_code,
            },
        )


def completed_legacy_checksum(user_id: str, source_key: str) -> str | None:
    with _tenant_connection(user_id) as connection:
        row = connection.execute(
            """
            SELECT source_checksum FROM portfolio_legacy_imports
            WHERE source_key = %(source_key)s AND status = 'completed'
            """,
            {"source_key": source_key},
        ).fetchone()
    return str(row["source_checksum"]) if row else None
