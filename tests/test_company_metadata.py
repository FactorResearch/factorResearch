from codes.data import company_metadata as cm


def _isolate(monkeypatch):
    monkeypatch.setattr(cm, "_map", None)
    store = {}
    monkeypatch.setattr(cm.cache, "read", lambda kind, key: store.get((kind, key)))
    monkeypatch.setattr(cm.cache, "write", lambda kind, key, data, **kw: store.update({(kind, key): data}))


def test_record_and_get_metadata(monkeypatch):
    _isolate(monkeypatch)
    cm.record_sector("AAPL", "Technology", sic=3674, exchange="Nasdaq")
    m = cm.get_metadata_map()
    assert m["AAPL"]["sector"] == "Technology"
    assert m["AAPL"]["sic"] == 3674


def test_record_sector_noop_on_empty(monkeypatch):
    _isolate(monkeypatch)
    cm.record_sector("AAPL", "")
    assert cm.get_metadata_map() == {}


def test_enrich_rows_fills_missing_sector_only(monkeypatch):
    _isolate(monkeypatch)
    cm.record_sector("AAPL", "Technology")
    rows = [
        {"symbol": "AAPL", "sector": ""},
        {"symbol": "MSFT", "sector": "Already Set"},
        {"symbol": "ZZZZ", "sector": ""},
    ]
    n = cm.enrich_rows(rows)
    assert n == 1
    assert rows[0]["sector"] == "Technology"
    assert rows[1]["sector"] == "Already Set"
    assert rows[2]["sector"] == ""


def test_enrich_rows_empty_cache_is_noop(monkeypatch):
    _isolate(monkeypatch)
    assert cm.enrich_rows([{"symbol": "AAPL", "sector": ""}]) == 0