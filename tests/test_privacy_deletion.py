from contextlib import contextmanager
from unittest.mock import MagicMock, Mock

from codes.data import analytics_db, db
from codes.services import analysis_snapshot_service


@contextmanager
def _connection(connection):
    yield connection


def test_delete_user_records_covers_all_user_tables(monkeypatch):
    connection = MagicMock()
    connection.execute.return_value.rowcount = 1
    monkeypatch.setattr(db, "_ensure_user_init", lambda: None)
    monkeypatch.setattr(db, "_users_conn", lambda: _connection(connection))
    result = db.delete_user_records("user-1")
    assert result == {
        "portfolio_simulation_results": 1,
        "portfolio_transactions": 1,
        "portfolio_holdings": 1,
        "portfolio_tombstones": 1,
        "portfolio_legacy_imports": 1,
        "portfolios": 1,
        "idempotency_records": 1,
        "user_weights": 1,
        "user_usage": 1,
        "subscriptions": 1,
        "user_settings": 1,
    }
    # One tenant-context statement plus one owner-scoped delete per table.
    assert connection.execute.call_count == 12


def test_delete_analytics_matches_authenticated_and_anonymous_identity(monkeypatch):
    connection = Mock()
    connection.execute.return_value.rowcount = 4
    monkeypatch.setattr(analytics_db, "ensure_schema", lambda: None)
    monkeypatch.setattr(analytics_db, "_conn", lambda: _connection(connection))
    assert analytics_db.delete_identity_events("user-1") == 4
    query = connection.execute.call_args.args[0]
    assert "user_id" in query and "anonymous_id" in query


def test_delete_private_snapshots_is_owner_scoped(monkeypatch):
    cursor = Mock()
    cursor.rowcount = 2
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    monkeypatch.setattr(analysis_snapshot_service, "_connect", lambda: _connection(connection))
    assert analysis_snapshot_service.delete_user_snapshots("user-1") == 2
    assert "WHERE user_id = %s" in cursor.execute.call_args.args[0]
