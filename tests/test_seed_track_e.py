import pytest

from scripts import seed_track_e


def test_seed_refuses_missing_or_remote_database(monkeypatch):
    monkeypatch.delenv("FLASK_ENV", raising=False)
    with pytest.raises(RuntimeError, match="required"):
        seed_track_e._assert_safe_database(None)
    with pytest.raises(RuntimeError, match="non-local"):
        seed_track_e._assert_safe_database("postgresql://db.example.com/prod")


def test_seed_refuses_production_even_on_localhost(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    with pytest.raises(RuntimeError, match="production"):
        seed_track_e._assert_safe_database("postgresql://localhost/factorresearch_market")


def test_seed_is_deterministic(monkeypatch):
    monkeypatch.setenv("DATABASE_MARKET_URL", "postgresql://localhost/factorresearch_market")
    monkeypatch.setenv("FLASK_ENV", "development")
    calls = {"prices": 0}
    monkeypatch.setattr(seed_track_e.temporal, "ensure_schema", lambda: None)
    monkeypatch.setattr(seed_track_e.temporal, "register_security", lambda *args, **kwargs: None)
    monkeypatch.setattr(seed_track_e.temporal, "add_identifier", lambda *args, **kwargs: None)
    monkeypatch.setattr(seed_track_e.temporal, "upsert_corporate_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(seed_track_e.temporal, "upsert_price", lambda *args, **kwargs: calls.__setitem__("prices", calls["prices"] + 1))
    monkeypatch.setattr(seed_track_e.temporal, "record_filing", lambda filing, _facts: filing["filing_id"])
    monkeypatch.setattr(seed_track_e.temporal, "record_symbol_change", lambda *args, **kwargs: None)
    monkeypatch.setattr(seed_track_e.temporal, "mark_delisted", lambda *args, **kwargs: None)
    monkeypatch.setattr(seed_track_e.temporal, "replace_universe_history", lambda *args, **kwargs: 3)
    monkeypatch.setattr(seed_track_e.temporal, "upsert_fx_rate", lambda *args, **kwargs: None)
    monkeypatch.setattr(seed_track_e.temporal, "checkpoint", lambda *args, **kwargs: None)
    monkeypatch.setattr(seed_track_e.temporal, "coverage_report", lambda: {"securities": 3})

    first = seed_track_e.seed()
    first_id = seed_track_e._id("security", "ACME")
    second_id = seed_track_e._id("security", "ACME")
    assert first_id == second_id
    assert first["fixtures"] == ["ACME", "NIMB", "OLD"]
    assert first["price_rows"] == calls["prices"] == 234
