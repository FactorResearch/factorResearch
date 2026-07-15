from unittest.mock import Mock

from codes.data import migrate


def test_release_migration_initializes_each_schema_once(monkeypatch):
    market = Mock()
    users = Mock()
    snapshots = Mock()
    monkeypatch.setattr(migrate.db, "init_db", market)
    monkeypatch.setattr(migrate.db, "init_user_db", users)
    monkeypatch.setattr(migrate, "ensure_schema_if_configured", snapshots)

    migrate.main()

    market.assert_called_once_with()
    users.assert_called_once_with()
    snapshots.assert_called_once_with()
