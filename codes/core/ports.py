"""Narrow, framework-neutral ports for volatile application boundaries.

Protocols live beside stable application contracts. Concrete HTTP, database,
cache, and framework adapters belong in infrastructure-facing modules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Time source used by application code that must be deterministic in tests."""

    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...


class IdGenerator(Protocol):
    """Opaque identifier source."""

    def new_id(self) -> str: ...


class QuoteReader(Protocol):
    """Read a normalized quote without exposing a vendor response shape."""

    def get_quote(self, symbol: str) -> Mapping[str, float | str | None]: ...


class FilingReader(Protocol):
    """Read normalized filing summaries for one company."""

    def get_filings(self, symbol: str) -> Sequence[Mapping[str, object]]: ...


class TickerUniverseReader(Protocol):
    """Read normalized ticker symbols without exposing provider payloads."""

    def read_tickers(self) -> Sequence[str]: ...


class AnalyticsContext(Protocol):
    """Request/session facts required by product analytics policy."""

    def anonymous_id(self) -> str | None: ...

    def authenticated_user_id(self) -> str | None: ...

    def page_path(self) -> str | None: ...

    def is_opted_out(self) -> bool: ...

    def set_opt_out(self, opt_out: bool) -> None: ...


class AnalysisRepository(Protocol):
    """Persist and retrieve domain-oriented analysis snapshots."""

    def get_latest(self, symbol: str) -> Mapping[str, object] | None: ...

    def save(self, symbol: str, analysis: Mapping[str, object]) -> None: ...
