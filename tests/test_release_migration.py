from unittest.mock import Mock

from codes.data import migrate


def test_release_migration_initializes_each_schema_once(monkeypatch):
    market = Mock()
    users = Mock()
    analytics = Mock()
    grants = Mock()
    monkeypatch.setattr(migrate.db, "init_db", market)
    monkeypatch.setattr(migrate.db, "init_user_db", users)
    monkeypatch.setattr(migrate.db, "configure_users_runtime_role", grants)
    monkeypatch.setattr(migrate.db, "_db_url", Mock(return_value="postgresql://market"))
    monkeypatch.setattr(
        migrate.db,
        "_users_db_url",
        Mock(return_value="postgresql://runtime_users@users/database"),
    )
    monkeypatch.setattr(migrate, "_initialize_analytics_schema", analytics)
    monkeypatch.setattr(migrate, "_analytics_runtime_url", Mock(return_value=None))
    monkeypatch.setattr(migrate, "is_production", Mock(return_value=False))

    migrate.main()

    market.assert_called_once_with(
        "postgresql://market",
        additional_bootstrap_sql=(migrate.temporal.SCHEMA,),
        lock_timeout_seconds=30.0,
    )
    users.assert_called_once_with(
        "postgresql://runtime_users@users/database", lock_timeout_seconds=30.0
    )
    analytics.assert_called_once_with(
        "postgresql://market",
        lock_timeout_seconds=30.0,
    )
    grants.assert_called_once_with("postgresql://runtime_users@users/database", "runtime_users")
