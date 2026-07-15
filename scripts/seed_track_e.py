"""Populate a local market database with deterministic Track E research data."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import uuid
from urllib.parse import urlparse

from dotenv import load_dotenv

from codes.data import temporal

load_dotenv()

_SEED_NAMESPACE = uuid.UUID("bb041d4c-a615-4b38-a3ee-64b34a26795f")
_LOCAL_HOSTS = {None, "", "localhost", "127.0.0.1", "::1"}


def _id(kind: str, value: str) -> str:
    return str(uuid.uuid5(_SEED_NAMESPACE, f"{kind}:{value}"))


def _assert_safe_database(url: str | None) -> None:
    if not url:
        raise RuntimeError("DATABASE_MARKET_URL is required.")
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("Track E seeds require PostgreSQL.")
    if parsed.hostname not in _LOCAL_HOSTS:
        raise RuntimeError("Refusing to seed a non-local database host.")
    if os.environ.get("FLASK_ENV", "").lower() == "production":
        raise RuntimeError("Refusing to seed while FLASK_ENV=production.")


def _security(symbol: str, name: str, *, status: str = "active") -> temporal.SecurityIdentity:
    return temporal.SecurityIdentity(
        security_id=_id("security", symbol), entity_id=_id("entity", name),
        legal_name=name, symbol=symbol, market_code="US", exchange_code="TESTX",
        currency="USD",
    )


def _seed_identity(identity: temporal.SecurityIdentity, identifiers: dict[str, str]) -> None:
    temporal.register_security(identity, source="track_e_seed", confidence="issuer_verified")
    for namespace, value in identifiers.items():
        temporal.add_identifier(identity.security_id, namespace, value, source="track_e_seed", confidence="issuer_verified")


def _filing(identity: temporal.SecurityIdentity, document: str, filed_at: str, revenue: float, net_income: float, *, supersedes: str | None = None) -> str:
    facts = [
        {"statement_type": "income", "fact_name": "revenue", "period_end": "2023-12-31", "fiscal_year": 2023, "fiscal_period": "FY", "value": revenue, "unit": "USD", "currency": "USD", "confidence": "issuer_verified"},
        {"statement_type": "income", "fact_name": "net_income", "period_end": "2023-12-31", "fiscal_year": 2023, "fiscal_period": "FY", "value": net_income, "unit": "USD", "currency": "USD", "confidence": "issuer_verified"},
    ]
    return temporal.record_filing({
        "filing_id": _id("filing", document), "security_id": identity.security_id,
        "document_id": document, "form_type": "10-K/A" if supersedes else "10-K",
        "period_end": "2023-12-31", "filed_at": filed_at, "accepted_at": filed_at,
        "source": "track_e_seed", "source_url": f"https://example.invalid/filings/{document}",
        "content_hash": _id("hash", document).replace("-", ""), "supersedes_id": supersedes,
    }, facts)


def _seed_actions(identity: temporal.SecurityIdentity) -> None:
    actions = [
        {"action_type": "split", "provider_event_id": f"{identity.symbol}-split-2024", "effective_date": "2024-06-03", "ratio": 2.0},
        {"action_type": "dividend", "provider_event_id": f"{identity.symbol}-div-2025q1", "announced_at": "2025-01-15", "effective_date": "2025-02-14", "ex_date": "2025-02-14", "record_date": "2025-02-18", "payment_date": "2025-03-03", "amount": 0.25, "currency": "USD"},
    ]
    for action in actions:
        temporal.upsert_corporate_action({"security_id": identity.security_id, "source": "track_e_seed", "source_url": None, **action})


def _seed_prices(identity: temporal.SecurityIdentity, start_price: float) -> int:
    start = dt.date(2024, 1, 2)
    count = 0
    for offset in range(0, 540, 7):
        date = start + dt.timedelta(days=offset)
        close = round(start_price * (1 + offset / 5000), 2)
        temporal.upsert_price({
            "security_id": identity.security_id, "price_date": date,
            "open": close - 0.4, "high": close + 0.8, "low": close - 0.9,
            "close": close, "adjusted_close": close, "volume": 1_000_000 + offset * 100,
            "currency": "USD", "adjustment_version": "track-e-seed-v1", "source": "track_e_seed",
        })
        count += 1
    return count


def seed() -> dict:
    _assert_safe_database(os.environ.get("DATABASE_MARKET_URL"))
    temporal.ensure_schema()
    acme = _security("ACME", "Acme Industrial Holdings")
    nimbus = _security("NIMB", "Nimbus Software Group")
    oldco = _security("OLD", "Old Company Research Fixture")
    fixtures = [
        (acme, {"CIK": "0001000001", "CUSIP": "004000101", "ISIN": "US0040001010", "SEDOL": "B000001"}, 42.0),
        (nimbus, {"CIK": "0001000002", "CUSIP": "654000102", "ISIN": "US6540001020", "SEDOL": "B000002"}, 88.0),
        (oldco, {"CIK": "0001000003", "CUSIP": "680000103", "ISIN": "US6800001030", "SEDOL": "B000003"}, 16.0),
    ]
    price_rows = 0
    for identity, identifiers, price in fixtures:
        _seed_identity(identity, identifiers)
        _seed_actions(identity)
        price_rows += _seed_prices(identity, price)

    original = _filing(acme, "ACME-2023-10K", "2024-02-15T16:00:00+00:00", 1_000_000_000, 100_000_000)
    _filing(acme, "ACME-2023-10KA", "2024-05-01T16:00:00+00:00", 980_000_000, 82_000_000, supersedes=original)
    _filing(nimbus, "NIMB-2023-10K", "2024-03-01T16:00:00+00:00", 650_000_000, 75_000_000)
    _filing(oldco, "OLD-2023-10K", "2024-03-10T16:00:00+00:00", 210_000_000, 12_000_000)

    temporal.record_symbol_change(nimbus.security_id, "NIMB", "NMBX", dt.date(2025, 1, 2), market_code="US", source="track_e_seed")
    temporal.mark_delisted(oldco.security_id, dt.date(2025, 6, 30))
    temporal.replace_universe_history("TEST500", "Track E Test 500", [
        {"security_id": acme.security_id, "valid_from": "2020-01-01", "valid_to": None},
        {"security_id": nimbus.security_id, "valid_from": "2022-01-01", "valid_to": None},
        {"security_id": oldco.security_id, "valid_from": "2020-01-01", "valid_to": "2025-06-30"},
    ], source="track_e_seed")
    for date, rate in (("2024-01-02", 1.34), ("2025-01-02", 1.39), ("2026-01-02", 1.37)):
        temporal.upsert_fx_rate({"base_currency": "USD", "quote_currency": "CAD", "rate_date": date, "rate": rate, "source": "track_e_seed"})
    temporal.checkpoint("seed", "track-e", status="complete", rows_written=price_rows)
    return {"fixtures": [identity.symbol for identity, _, _ in fixtures], "price_rows": price_rows, "coverage": temporal.coverage_report(), "urls": ["/data/ACME", "/data/NMBX", "/data/OLD"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(seed(), indent=2, default=str))


if __name__ == "__main__":
    main()
