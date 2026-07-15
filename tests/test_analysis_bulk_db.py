from contextlib import contextmanager

from codes.data import db


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Connection:
    row_factory = None

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return _Result(self.rows)


@contextmanager
def _connection(conn):
    yield conn


def test_analysis_entry_decoder_rejects_invalid_payloads():
    assert db._analysis_entry_from_row(None) is None
    assert db._analysis_entry_from_row({"data_json": "invalid", "updated_at": "now"}) is None
    assert db._analysis_entry_from_row({"data_json": '{"symbol":"AAPL"}', "updated_at": "now"}) == {
        "data": {"symbol": "AAPL"},
        "updated_at": "now",
    }


def test_targeted_analysis_read_normalizes_and_skips_invalid_rows(monkeypatch):
    conn = _Connection([
        {"ticker": "AAPL", "data_json": '{"symbol":"AAPL"}', "updated_at": "today"},
        {"ticker": "MSFT", "data_json": "invalid", "updated_at": "today"},
    ])
    monkeypatch.setattr(db, "_ensure_init", lambda: None)
    monkeypatch.setattr(db, "_conn", lambda: _connection(conn))

    assert db.get_analysis_entries([" aapl ", "AAPL", "msft"]) == {
        "AAPL": {"data": {"symbol": "AAPL"}, "updated_at": "today"}
    }
    assert conn.calls[0][1] == {"tickers": ["AAPL", "MSFT"]}


def test_targeted_analysis_read_short_circuits_empty_input(monkeypatch):
    initialize = lambda: (_ for _ in ()).throw(AssertionError("database should not initialize"))
    monkeypatch.setattr(db, "_ensure_init", initialize)

    assert db.get_analysis_entries([]) == {}
