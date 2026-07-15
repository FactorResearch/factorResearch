import datetime as dt
from contextlib import contextmanager
from types import SimpleNamespace

from codes.data import temporal
from codes.data.providers.fmp import FMPClient, FMPError
from codes.services import track_e_ingestion


class _Result:
    def __init__(self, rows=None):
        self.rows = rows or []

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []
        self.row_factory = None

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return _Result(self.rows)


def _connection(conn):
    @contextmanager
    def context():
        yield conn
    return context


def test_security_registration_is_relational_and_idempotent(monkeypatch):
    conn = _Connection()
    monkeypatch.setattr(temporal, "ensure_schema", lambda: None)
    monkeypatch.setattr(temporal.db, "_conn", _connection(conn))
    identity = temporal.SecurityIdentity("00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002", "Example Inc", "TEST", "US", "NASDAQ", "USD")

    assert temporal.register_security(identity, source="fmp") == identity.security_id
    assert any("security_entities" in sql and "ON CONFLICT" in sql for sql, _ in conn.calls)
    assert any("security_identifiers" in sql and "TICKER" in sql for sql, _ in conn.calls)


def test_as_of_facts_filter_public_availability(monkeypatch):
    conn = _Connection([{"fact_name": "revenue", "value": 10.0}])
    monkeypatch.setattr(temporal, "ensure_schema", lambda: None)
    monkeypatch.setattr(temporal.db, "_conn", _connection(conn))
    as_of = dt.datetime(2020, 4, 1, tzinfo=dt.timezone.utc)

    assert temporal.get_facts_as_of("security", as_of)[0]["value"] == 10.0
    sql, params = conn.calls[-1]
    assert "available_at <= %(as_of)s" in sql
    assert params["as_of"] == as_of


def test_security_resolution_uses_non_nullable_scope_query(monkeypatch):
    conn = _Connection([{"security_id": "s", "identifier": "ESNT"}])
    monkeypatch.setattr(temporal, "ensure_schema", lambda: None)
    monkeypatch.setattr(temporal.db, "_conn", _connection(conn))
    assert temporal.resolve_security("TICKER", "ESNT", market_code="US")["security_id"] == "s"
    sql, params = conn.calls[-1]
    assert "i.scope=%(market_code)s" in sql
    assert "market_code)s IS NULL" not in sql
    assert params["market_code"] == "US"


def test_fx_identity_and_historical_lookup(monkeypatch):
    assert temporal.get_fx_rate("USD", "USD", dt.date(2020, 1, 1)) == 1.0
    conn = _Connection([(1.25,)])
    monkeypatch.setattr(temporal, "ensure_schema", lambda: None)
    monkeypatch.setattr(temporal.db, "_conn", _connection(conn))
    assert temporal.get_fx_rate("CAD", "USD", dt.date(2020, 1, 1)) == 1.25
    assert "rate_date <= %(date)s" in conn.calls[-1][0]


def test_fmp_client_requires_secret(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    try:
        FMPClient()
    except FMPError as exc:
        assert "FMP_API_KEY" in str(exc)
    else:
        raise AssertionError("missing FMP key must fail closed")


def test_fmp_uses_header_auth_and_stable_endpoint(monkeypatch):
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: [{"symbol": "AAPL"}])
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(url=url, **kwargs)
        return response

    monkeypatch.setattr("codes.data.providers.fmp.requests.get", fake_get)
    monkeypatch.setattr("codes.data.providers.fmp.provider_gateway.call", lambda _provider, _operation, callback, **_kwargs: callback())
    assert FMPClient("secret").profile("aapl")["symbol"] == "AAPL"
    assert seen["url"].endswith("/stable/profile")
    assert seen["headers"] == {"apikey": "secret"}


def test_identity_normalization_does_not_leak_provider_payload(monkeypatch):
    client = SimpleNamespace(profile=lambda _symbol: {"companyName": "Example", "country": "US", "currency": "USD", "exchangeShortName": "NASDAQ", "cik": "123"})
    captured = {}
    monkeypatch.setattr(track_e_ingestion.temporal, "register_security", lambda identity, **_kwargs: captured.setdefault("identity", identity) or identity.security_id)
    monkeypatch.setattr(track_e_ingestion.temporal, "add_identifier", lambda *args, **kwargs: None)
    result = track_e_ingestion.ingest_identity("test", client)
    assert result["security_id"] == captured["identity"].security_id
    assert captured["identity"].symbol == "TEST"
    assert not hasattr(captured["identity"], "exchangeShortName")

