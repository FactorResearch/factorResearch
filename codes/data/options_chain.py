"""Provider-neutral option-chain models and provider adapters.

Network access belongs in providers; scoring models consume only the normalized
``OptionsChainSnapshot`` shape.  This keeps the options engine deterministic and
makes adding another vendor an adapter change instead of a model rewrite.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Callable, Protocol, runtime_checkable


class OptionsChainProviderError(RuntimeError):
    """Raised when a provider cannot return a valid option-chain response."""


@dataclass(frozen=True)
class OptionContract:
    """Normalized market quote and metadata for one listed option contract."""

    contract_symbol: str | None
    option_type: str
    expiration_date: str
    days_to_expiry: int
    strike: float
    bid: float | None
    ask: float | None
    mid: float | None
    spread_pct: float | None
    last_price: float | None
    volume: int | None
    open_interest: int | None
    implied_volatility: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    rho: float | None
    theoretical_value: float | None
    intrinsic_value: float | None
    time_value: float | None
    contract_size: str | None
    contract_multiplier: int | None
    currency: str | None
    in_the_money: bool | None
    last_trade_at: str | None
    updated_at: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class OptionsChainSnapshot:
    """Normalized point-in-time chain returned by any provider adapter."""

    symbol: str
    provider: str
    status: str
    fetched_at: str
    exchange: str | None
    contracts: tuple[OptionContract, ...]
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "provider": self.provider,
            "status": self.status,
            "fetched_at": self.fetched_at,
            "exchange": self.exchange,
            "contract_count": len(self.contracts),
            "contracts": [contract.to_dict() for contract in self.contracts],
            "error": self.error,
        }


@runtime_checkable
class OptionsChainProvider(Protocol):
    """Interface implemented by live option-chain vendors."""

    name: str

    def fetch_chain(self, symbol: str) -> OptionsChainSnapshot:
        """Fetch and normalize the current chain for ``symbol``."""


def unavailable_chain(
    symbol: str,
    *,
    provider: str,
    status: str,
    error: str | None = None,
    fetched_at: datetime | None = None,
) -> dict:
    """Return the stable empty-chain shape used for graceful degradation."""
    timestamp = _as_utc(fetched_at or datetime.now(timezone.utc)).isoformat()
    return OptionsChainSnapshot(
        symbol=symbol.upper().strip(),
        provider=provider,
        status=status,
        fetched_at=timestamp,
        exchange=None,
        contracts=(),
        error=error,
    ).to_dict()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _finite_number(value: object, *, minimum: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        return None
    return result


def _non_negative_int(value: object) -> int | None:
    number = _finite_number(value, minimum=0)
    return int(number) if number is not None else None


def _first(mapping: dict, *keys: str) -> object | None:
    for key in keys:
        if key in mapping and mapping[key] is not None and mapping[key] != "":
            return mapping[key]
    return None


def _iso_datetime(value: object) -> str | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)):
            timestamp = float(value)
            # Some market-data fields use milliseconds.
            if timestamp > 10_000_000_000:
                timestamp /= 1000.0
            parsed = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        else:
            raw = str(value).strip().replace("Z", "+00:00")
            parsed = datetime.fromisoformat(raw)
            parsed = _as_utc(parsed)
        return parsed.isoformat()
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _iso_date(value: object) -> str | None:
    timestamp = _iso_datetime(value)
    if timestamp is not None:
        return timestamp[:10]
    try:
        return date.fromisoformat(str(value).strip()[:10]).isoformat()
    except (TypeError, ValueError):
        return None


def _optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _contract_multiplier(contract_size: object) -> int | None:
    numeric = _non_negative_int(contract_size)
    if numeric:
        return numeric
    normalized = str(contract_size or "").strip().upper()
    if normalized == "REGULAR":
        return 100
    if normalized == "MINI":
        return 10
    return None


def _normalize_contract(
    row: dict,
    *,
    option_type: str,
    group_expiration: object,
    fetched_date: date,
) -> OptionContract | None:
    normalized_type = str(_first(row, "type", "optionType") or option_type).strip().upper()
    if normalized_type not in {"CALL", "PUT"}:
        return None

    expiration = _iso_date(
        _first(row, "expirationDate", "expiration", "expiry", "expiration_date")
        or group_expiration
    )
    strike = _finite_number(_first(row, "strike", "strikePrice"), minimum=0)
    if expiration is None or strike is None or strike <= 0:
        return None

    try:
        days_to_expiry = max((date.fromisoformat(expiration) - fetched_date).days, 0)
    except ValueError:
        return None

    bid = _finite_number(_first(row, "bid", "bidPrice"), minimum=0)
    ask = _finite_number(_first(row, "ask", "askPrice"), minimum=0)
    mid = None
    spread_pct = None
    if bid is not None and ask is not None and ask >= bid and ask > 0:
        mid = (bid + ask) / 2.0
        if mid > 0:
            spread_pct = (ask - bid) / mid

    implied_volatility = _finite_number(
        _first(row, "impliedVolatility", "implied_volatility", "iv"), minimum=0
    )
    if implied_volatility == 0:
        implied_volatility = None

    contract_size_raw = _first(row, "contractSize", "contract_size", "multiplier")
    contract_size = str(contract_size_raw).strip() if contract_size_raw is not None else None
    contract_symbol_raw = _first(row, "contractName", "contractSymbol", "symbol")
    currency_raw = _first(row, "currency")

    return OptionContract(
        contract_symbol=(str(contract_symbol_raw).strip() if contract_symbol_raw else None),
        option_type=normalized_type,
        expiration_date=expiration,
        days_to_expiry=days_to_expiry,
        strike=round(strike, 6),
        bid=round(bid, 6) if bid is not None else None,
        ask=round(ask, 6) if ask is not None else None,
        mid=round(mid, 6) if mid is not None else None,
        spread_pct=round(spread_pct, 6) if spread_pct is not None else None,
        last_price=(
            round(value, 6)
            if (value := _finite_number(_first(row, "lastPrice", "last", "mark"), minimum=0)) is not None
            else None
        ),
        volume=_non_negative_int(_first(row, "volume")),
        open_interest=_non_negative_int(_first(row, "openInterest", "open_interest")),
        implied_volatility=(round(implied_volatility, 8) if implied_volatility is not None else None),
        delta=_finite_number(_first(row, "delta")),
        gamma=_finite_number(_first(row, "gamma")),
        theta=_finite_number(_first(row, "theta")),
        vega=_finite_number(_first(row, "vega")),
        rho=_finite_number(_first(row, "rho")),
        theoretical_value=_finite_number(_first(row, "theoretical", "theoreticalValue"), minimum=0),
        intrinsic_value=_finite_number(_first(row, "intrinsicValue", "intrinsic_value"), minimum=0),
        time_value=_finite_number(_first(row, "timeValue", "time_value"), minimum=0),
        contract_size=contract_size,
        contract_multiplier=_contract_multiplier(contract_size_raw),
        currency=(str(currency_raw).strip().upper() if currency_raw else None),
        in_the_money=_optional_bool(_first(row, "inTheMoney", "in_the_money")),
        last_trade_at=_iso_datetime(_first(row, "lastTradeDateTime", "lastTradeDate", "last_trade_at")),
        updated_at=_iso_datetime(_first(row, "updatedAt", "updated_at")),
    )


def normalize_finnhub_chain(
    payload: object,
    symbol: str,
    *,
    fetched_at: datetime | None = None,
) -> OptionsChainSnapshot:
    """Normalize Finnhub's nested expiration/CALL/PUT response."""
    if not isinstance(payload, dict):
        raise OptionsChainProviderError("Finnhub returned a non-object option-chain payload")
    if payload.get("error"):
        raise OptionsChainProviderError(str(payload["error"]))

    fetched = _as_utc(fetched_at or datetime.now(timezone.utc))
    groups = payload.get("data")
    if not isinstance(groups, list):
        groups = [payload] if isinstance(payload.get("options"), dict) else []

    contracts: list[OptionContract] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        expiration = _first(group, "expirationDate", "expiration", "expiry")
        options = group.get("options")
        if not isinstance(options, dict):
            continue
        for option_type in ("CALL", "PUT"):
            rows = options.get(option_type)
            if rows is None:
                rows = options.get(option_type.lower())
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                contract = _normalize_contract(
                    row,
                    option_type=option_type,
                    group_expiration=expiration,
                    fetched_date=fetched.date(),
                )
                if contract is not None:
                    contracts.append(contract)

    contracts.sort(
        key=lambda contract: (
            contract.expiration_date,
            contract.option_type,
            contract.strike,
            contract.contract_symbol or "",
        )
    )
    exchange_raw = payload.get("exchange")
    return OptionsChainSnapshot(
        symbol=symbol.upper().strip(),
        provider="FINNHUB",
        status="AVAILABLE" if contracts else "NO_DATA",
        fetched_at=fetched.isoformat(),
        exchange=str(exchange_raw).strip() if exchange_raw else None,
        contracts=tuple(contracts),
    )


class FinnhubOptionsChainProvider:
    """Live Finnhub adapter using an injected SDK client and rate-limit hooks."""

    name = "FINNHUB"

    def __init__(
        self,
        client: object,
        *,
        before_request: Callable[[], None] | None = None,
        after_request: Callable[[], None] | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self._client = client
        self._before_request = before_request
        self._after_request = after_request
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def fetch_chain(self, symbol: str) -> OptionsChainSnapshot:
        normalized_symbol = symbol.upper().strip()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        if self._before_request is not None:
            self._before_request()
        try:
            payload = self._client.option_chain(symbol=normalized_symbol)
        except Exception as exc:
            raise OptionsChainProviderError(
                f"Finnhub option-chain request failed: {type(exc).__name__}"
            ) from exc
        if self._after_request is not None:
            self._after_request()
        return normalize_finnhub_chain(payload, normalized_symbol, fetched_at=self._clock())
