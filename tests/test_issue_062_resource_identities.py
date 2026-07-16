"""Acceptance coverage for ISSUE_062 platform-neutral resource identities."""

from __future__ import annotations

import uuid

import pytest

from codes import portfolio
from codes.data import cache
from codes.services import track_e_ingestion, user_settings


@pytest.fixture()
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "yi1myb0TPr6CavFrLrf1lgV6MChXb5VSNK4FDqFpdlw=")
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache._encryptor = None
    yield
    cache._encryptor = None


def test_security_id_uses_global_identifier_not_symbol() -> None:
    first = track_e_ingestion._security_uuid({"isin": "US0378331005", "symbol": "AAPL"})
    renamed = track_e_ingestion._security_uuid({"isin": "US0378331005", "symbol": "APPL"})

    assert first == renamed
    assert uuid.UUID(first)


def test_security_without_global_identifier_gets_opaque_id() -> None:
    first = track_e_ingestion._security_uuid({"symbol": "SAME"})
    second = track_e_ingestion._security_uuid({"symbol": "SAME"})

    assert first != second
    assert uuid.UUID(first)


def test_portfolio_name_is_an_alias_for_permanent_id(isolated_cache) -> None:
    created = portfolio.create_portfolio("user-1", "Original name")
    resource_id = created["id"]
    created["name"] = "Renamed"
    portfolio.save_portfolio("user-1", created)

    assert portfolio.list_portfolios("user-1") == ["Renamed"]
    assert portfolio.load_portfolio("user-1", "Renamed")["id"] == resource_id
    assert portfolio.load_portfolio("user-1", "Original name") is None


def test_holding_keeps_security_id_when_symbol_is_only_an_alias(isolated_cache, monkeypatch) -> None:
    monkeypatch.setattr(
        portfolio.temporal,
        "resolve_security",
        lambda *_args, **_kwargs: {"security_id": "security-123"},
    )
    portfolio.create_portfolio("user-1", "Core")

    updated, error = portfolio.add_holding("user-1", "Core", "OLD", 5, 10.0, "Issuer")

    assert error == ""
    assert updated["holdings"]["OLD"]["security_id"] == "security-123"

    monkeypatch.setattr(
        portfolio.temporal,
        "get_security_identity",
        lambda _security_id: {"security_id": "security-123", "symbol": "NEW"},
    )
    reloaded = portfolio.load_portfolio("user-1", "Core")
    assert "NEW" in reloaded["holdings"]
    assert reloaded["holdings"]["NEW"]["security_id"] == "security-123"


def test_new_saved_view_id_is_independent_of_name(monkeypatch) -> None:
    stored = {}
    monkeypatch.setattr(user_settings.db, "get_user_settings", lambda _user_id: stored)
    monkeypatch.setattr(
        user_settings.db,
        "upsert_user_settings",
        lambda _user_id, settings: stored.update(settings) or settings,
    )

    settings = user_settings.add_saved_screener(
        "user-1", name="Value", market="US", sector="", indexes=[]
    )

    saved = settings["saved_screeners"][0]
    assert saved["id"] != "value"
    assert uuid.UUID(saved["id"])
