import os
import pytest
from codes.data import db


def test_missing_market_url_raises(monkeypatch):
    # Full isolation: swap os.environ for a copy with the var stripped, so
    # no autouse fixture / dotenv plugin elsewhere can silently restore it.
    env_without_url = {k: v for k, v in os.environ.items() if k != "DATABASE_MARKET_URL"}
    monkeypatch.setattr(os, "environ", env_without_url)

    # Sanity check — if this fails, something outside this test is
    # re-injecting DATABASE_MARKET_URL (e.g. pytest-dotenv, an autouse
    # conftest fixture calling load_dotenv()). That's the real thing to fix.
    assert "DATABASE_MARKET_URL" not in os.environ

    db._PG_POOL = None
    with pytest.raises(RuntimeError, match="DATABASE_MARKET_URL"):
        db._db_url()