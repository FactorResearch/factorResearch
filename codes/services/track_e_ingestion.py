"""Normalization and ingestion orchestration for Track E datasets."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid

from codes.data import temporal
from codes.data.providers.fmp import FMPClient


def _security_uuid(profile: dict) -> str:
    for namespace, key in (("ISIN", "isin"), ("CUSIP", "cusip"), ("SEDOL", "sedol")):
        if value := str(profile.get(key) or "").strip().upper():
            return str(uuid.uuid5(uuid.NAMESPACE_URL, f"factorresearch:security:{namespace}:{value}"))
    return str(uuid.uuid4())


def _existing_security_id(profile: dict, symbol: str, market: str) -> str | None:
    identifiers = [
        (namespace, value, None)
        for namespace, key in (("ISIN", "isin"), ("CUSIP", "cusip"), ("SEDOL", "sedol"))
        if (value := profile.get(key))
    ]
    identifiers.append(("TICKER", symbol, market))
    for namespace, identifier, scope in identifiers:
        try:
            found = temporal.resolve_security(namespace, str(identifier), market_code=scope)
        except Exception:
            return None
        if found:
            return str(found["security_id"])
    return None


def _entity_uuid(profile: dict, security_id: str) -> str:
    stable = profile.get("cik") or profile.get("isin") or profile.get("cusip") or security_id
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"factorresearch:entity:{stable}"))


def _market_code(profile: dict, symbol: str) -> str:
    country = str(profile.get("country") or "").strip().upper()
    aliases = {"UNITED STATES": "US", "USA": "US", "CANADA": "CA", "UNITED KINGDOM": "GB", "UK": "GB"}
    if country in aliases:
        return aliases[country]
    if len(country) == 2 and country.isalpha():
        return country
    return "CA" if symbol.upper().endswith(".TO") else "US"


def ingest_identity(symbol: str, client: FMPClient) -> dict:
    profile = client.profile(symbol)
    market = _market_code(profile, symbol)
    security_id = _existing_security_id(profile, symbol, market) or _security_uuid(profile)
    identity = temporal.SecurityIdentity(
        security_id=security_id,
        entity_id=_entity_uuid(profile, security_id),
        legal_name=profile.get("companyName") or profile.get("companyNameLong") or symbol.upper(),
        symbol=symbol.upper(),
        market_code=market,
        exchange_code=profile.get("exchangeShortName") or profile.get("exchange"),
        currency=profile.get("currency"),
    )
    temporal.register_security(identity, source="fmp")
    for namespace, keys in {"CIK": ("cik",), "ISIN": ("isin",), "CUSIP": ("cusip",), "SEDOL": ("sedol",)}.items():
        value = next((profile.get(key) for key in keys if profile.get(key)), None)
        temporal.add_identifier(security_id, namespace, value, source="fmp")
    return {"security_id": security_id, "profile": profile}


def ingest_filings(symbol: str, security_id: str, client: FMPClient, *, years: int = 20) -> int:
    today = dt.date.today()
    filings = client.filings(symbol, str(today.replace(year=today.year - years)), str(today))
    count = 0
    for item in filings:
        document_id = str(item.get("accessionNumber") or item.get("accession") or item.get("finalLink") or item.get("link") or "")
        filed_at = item.get("acceptedDate") or item.get("fillingDate") or item.get("filingDate")
        if not document_id or not filed_at:
            continue
        temporal.record_filing({
            "security_id": security_id, "document_id": document_id,
            "form_type": item.get("formType") or item.get("type"),
            "period_end": item.get("periodOfReport"), "filed_at": filed_at,
            "accepted_at": item.get("acceptedDate"), "source": "fmp",
            "source_url": item.get("finalLink") or item.get("link"),
            "content_hash": hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode()).hexdigest(),
        }, [])
        count += 1
    return count


def ingest_fundamentals(symbol: str, security_id: str, client: FMPClient) -> int:
    """Normalize FMP as-reported rows into immutable filing-scoped facts."""
    metadata = {
        "symbol", "date", "period", "calendarYear", "fillingDate", "filingDate",
        "acceptedDate", "cik", "link", "finalLink", "reportedCurrency",
    }
    count = 0
    for row in client.statements_as_reported(symbol):
        period_end = row.get("date")
        filed_at = row.get("acceptedDate") or row.get("fillingDate") or row.get("filingDate")
        if not period_end or not filed_at:
            continue
        document_id = str(row.get("accessionNumber") or row.get("finalLink") or f"{symbol}:{period_end}:{row.get('period', 'FY')}")
        facts = []
        for name, value in row.items():
            if name in metadata or isinstance(value, bool):
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            facts.append({
                "statement_type": "as_reported", "fact_name": name,
                "period_end": period_end, "fiscal_year": int(row.get("calendarYear") or str(period_end)[:4]),
                "fiscal_period": row.get("period") or "FY", "value": numeric,
                "unit": row.get("reportedCurrency") or "number", "currency": row.get("reportedCurrency"),
                "confidence": "provider_normalized_internal_only", "available_at": filed_at,
            })
        temporal.record_filing({
            "security_id": security_id, "document_id": document_id,
            "form_type": row.get("period"), "period_end": period_end,
            "filed_at": filed_at, "accepted_at": row.get("acceptedDate"),
            "source": "fmp", "source_url": row.get("finalLink") or row.get("link"),
            "content_hash": hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest(),
        }, facts)
        count += len(facts)
    return count


def ingest_actions(symbol: str, security_id: str, client: FMPClient) -> int:
    count = 0
    for action_type, rows in (("split", client.splits(symbol)), ("dividend", client.dividends(symbol))):
        for item in rows:
            effective = item.get("date") or item.get("exDividendDate")
            if not effective:
                continue
            event_id = str(item.get("id") or f"{symbol}:{action_type}:{effective}")
            ratio = item.get("splitRatio")
            if ratio is None and item.get("numerator") and item.get("denominator"):
                ratio = float(item["numerator"]) / float(item["denominator"])
            temporal.upsert_corporate_action({
                "security_id": security_id, "action_type": action_type,
                "provider_event_id": event_id, "announced_at": item.get("declarationDate"),
                "effective_date": effective, "ex_date": item.get("exDividendDate"),
                "record_date": item.get("recordDate"), "payment_date": item.get("paymentDate"),
                "ratio": ratio, "amount": item.get("dividend") or item.get("adjDividend"),
                "currency": item.get("currency"), "source": "fmp", "source_url": None,
            })
            count += 1
    return count


def ingest_prices(symbol: str, security_id: str, currency: str, client: FMPClient) -> int:
    rows = client.prices(symbol)
    count = 0
    for item in rows:
        if item.get("date") is None or item.get("close") is None:
            continue
        temporal.upsert_price({
            "security_id": security_id, "price_date": item["date"],
            "open": item.get("open"), "high": item.get("high"), "low": item.get("low"),
            "close": item["close"], "adjusted_close": item.get("adjClose"),
            "volume": item.get("volume"), "currency": currency or "USD",
            "adjustment_version": "fmp-stable-v1", "source": "fmp",
        })
        count += 1
    return count


def ingest_fx(pair: str, client: FMPClient) -> int:
    pair = pair.upper()
    if len(pair) != 6:
        raise ValueError("FX pair must be six letters, for example EURUSD.")
    count = 0
    for item in client.fx_history(pair):
        if item.get("date") and item.get("close"):
            temporal.upsert_fx_rate({"base_currency": pair[:3], "quote_currency": pair[3:], "rate_date": item["date"], "rate": item["close"], "source": "fmp"})
            count += 1
    return count


def ingest_universe(code: str, client: FMPClient) -> int:
    rows = client.historical_constituents(code)
    memberships = []
    for item in rows:
        symbol = item.get("symbol") or item.get("addedSecurity") or item.get("removedSecurity")
        start = item.get("dateAdded") or item.get("addedDate") or item.get("date")
        if not symbol or not start:
            continue
        resolved = temporal.resolve_security("TICKER", symbol, dt.date.fromisoformat(str(start)[:10]))
        if not resolved:
            resolved = ingest_identity(symbol, client)
        security_id = resolved.get("security_id") if isinstance(resolved, dict) else resolved
        memberships.append({"security_id": security_id, "valid_from": str(start)[:10], "valid_to": item.get("dateRemoved") or item.get("removedDate")})
    names = {"SP500": "S&P 500", "NASDAQ": "Nasdaq", "DOWJONES": "Dow Jones Industrial Average"}
    return temporal.replace_universe_history(code, names.get(code.upper(), code.upper()), memberships, source="fmp")


def ingest_reference_data(client: FMPClient) -> dict[str, int]:
    changes = 0
    for item in client.symbol_changes():
        old_symbol = item.get("oldSymbol") or item.get("oldTicker")
        new_symbol = item.get("newSymbol") or item.get("newTicker")
        date = item.get("date") or item.get("effectiveDate")
        if not old_symbol or not new_symbol or not date:
            continue
        effective = dt.date.fromisoformat(str(date)[:10])
        identity = temporal.resolve_security("TICKER", old_symbol, effective)
        if identity:
            temporal.record_symbol_change(identity["security_id"], old_symbol, new_symbol, effective, market_code=identity.get("market_code") or "US", source="fmp")
            changes += 1
    delisted = 0
    page = 0
    while True:
        rows = client.delisted_companies(page=page, limit=100)
        if not rows:
            break
        for item in rows:
            symbol = item.get("symbol")
            date = item.get("delistedDate") or item.get("date")
            if not symbol or not date:
                continue
            identity = temporal.resolve_security("TICKER", symbol, dt.date.fromisoformat(str(date)[:10]))
            if identity:
                temporal.mark_delisted(identity["security_id"], dt.date.fromisoformat(str(date)[:10]))
                delisted += 1
        if len(rows) < 100:
            break
        page += 1
    return {"symbol_changes": changes, "delisted": delisted}


def ingest_symbol(symbol: str, client: FMPClient | None = None) -> dict:
    client = client or FMPClient()
    identity = ingest_identity(symbol, client)
    security_id, profile = identity["security_id"], identity["profile"]
    return {
        "symbol": symbol.upper(), "security_id": security_id,
        "filings": ingest_filings(symbol, security_id, client),
        "facts": ingest_fundamentals(symbol, security_id, client),
        "actions": ingest_actions(symbol, security_id, client),
        "prices": ingest_prices(symbol, security_id, profile.get("currency") or "USD", client),
    }
