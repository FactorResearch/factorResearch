import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from codes import portfolio
from codes.data import cache


@pytest.fixture()
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "ENCRYPTION_KEY",
        "yi1myb0TPr6CavFrLrf1lgV6MChXb5VSNK4FDqFpdlw=",
    )
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache._encryptor = None
    yield tmp_path
    cache._encryptor = None


def test_portfolio_crud_accepts_auth_provider_ids_and_spaced_names(isolated_cache):
    user_id = "auth0|abc123"
    name = "Long Term Value"

    created = portfolio.create_portfolio(user_id, name)
    assert created["name"] == name
    assert portfolio.list_portfolios(user_id) == [name]
    assert portfolio.load_portfolio(user_id, name)["name"] == name

    updated, err = portfolio.add_holding(user_id, name, "AAPL", 5, 150.0, "Apple Inc.")
    assert err == ""
    assert updated["holdings"]["AAPL"]["shares"] == 5
    assert portfolio.load_portfolio(user_id, name)["holdings"]["AAPL"]["name"] == "Apple Inc."

    portfolio.delete_portfolio(user_id, name)
    assert portfolio.list_portfolios(user_id) == []
    assert portfolio.load_portfolio(user_id, name) is None


def test_existing_safe_legacy_portfolio_keys_remain_readable(isolated_cache):
    user_id = "user1"
    name = "Growth"
    payload = {"name": name, "created": "2024-01-01T00:00:00", "holdings": {}}

    assert cache.write("portfolio", "user1_index", [name]) is True
    assert cache.write("portfolio", "user1_p_growth", payload) is True

    assert portfolio.list_portfolios(user_id) == [name]
    assert portfolio.load_portfolio(user_id, name) == payload


def test_portfolio_write_failures_are_not_silent(monkeypatch):
    monkeypatch.setattr(portfolio.cache, "write", lambda *args, **kwargs: False)

    with pytest.raises(RuntimeError):
        portfolio.create_portfolio("auth0|abc123", "Long Term Value")
