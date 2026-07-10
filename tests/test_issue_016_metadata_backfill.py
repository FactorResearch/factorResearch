import importlib
import os
import sys
from unittest.mock import patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from codes.data import company_metadata as cm


def _fresh_import_app():
    sys.modules.pop("codes.app", None)
    return importlib.import_module("codes.app")


def _isolate_metadata_cache(monkeypatch):
    monkeypatch.setattr(cm, "_map", None)
    monkeypatch.setattr(cm, "_refresh_running", False)
    monkeypatch.setattr(cm, "_refresh_last_call", 0.0)
    store = {}

    def fake_read(kind, key):
        return store.get((kind, key))

    def fake_write(kind, key, data, **kwargs):
        store[(kind, key)] = data
        return True

    monkeypatch.setattr(cm.cache, "read", fake_read)
    monkeypatch.setattr(cm.cache, "write", fake_write)
    return store


def test_app_startup_does_not_launch_metadata_backfill_by_default(monkeypatch):
    monkeypatch.delenv("COMPANY_METADATA_BACKFILL_ENABLED", raising=False)

    with patch("codes.data.sec_data.get_ticker_map", return_value={}), \
         patch("codes.data.db.init_db"), \
         patch("codes.engine.universe.get_universe", return_value=["AAPL", "MSFT"]), \
         patch("codes.engine.screener.load_cached_only", return_value=[]), \
         patch("codes.data.company_metadata.start_background_refresh") as refresh:
        _fresh_import_app()

    refresh.assert_not_called()


def test_background_refresh_is_disabled_by_default(monkeypatch):
    _isolate_metadata_cache(monkeypatch)
    monkeypatch.delenv("COMPANY_METADATA_BACKFILL_ENABLED", raising=False)

    with patch("codes.data.company_metadata.threading.Thread") as thread:
        started = cm.start_background_refresh(["AAPL", "MSFT"])

    assert started is False
    thread.assert_not_called()


def test_enabled_background_refresh_records_persisted_cooldown(monkeypatch):
    store = _isolate_metadata_cache(monkeypatch)
    monkeypatch.setenv("COMPANY_METADATA_BACKFILL_ENABLED", "1")
    monkeypatch.setenv("COMPANY_METADATA_BACKFILL_COOLDOWN_SECONDS", "3600")
    monkeypatch.setattr(cm, "_refresh_rate_wait", lambda: None)
    monkeypatch.setattr(cm.sec_data, "get_company_sector_light", lambda symbol: {})

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr(cm.threading, "Thread", ImmediateThread)

    assert cm.start_background_refresh(["AAPL", "MSFT"], max_symbols=1) is True
    assert cm.start_background_refresh(["AAPL", "MSFT"], max_symbols=1) is False

    state = store[(cm._KIND, cm._REFRESH_STATE_KEY)]
    assert state["symbol_count"] == 2
    assert state["max_symbols"] == 1
