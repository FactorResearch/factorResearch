"""Search supported company symbols without invoking financial analysis."""

from __future__ import annotations

import difflib
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

from codes.engine import screener

_CACHE_TTL_SECONDS = 300.0
_MAX_RESULTS = 8
_CORPORATE_SUFFIXES = re.compile(
    r"\b(incorporated|inc|corporation|corp|company|co|limited|ltd|plc)\b",
    re.IGNORECASE,
)
_INDEX_LOCK = threading.Lock()
_INDEX: tuple[float, tuple[dict[str, str], ...]] | None = None


@dataclass(frozen=True)
class CompanySuggestion:
    """A supported security choice suitable for an autocomplete result."""

    symbol: str
    name: str
    rank: tuple[int, int, str]

    def as_dict(self) -> dict[str, str]:
        """Return the stable presentation contract used by UI adapters."""
        return {"symbol": self.symbol, "name": self.name}


def normalize_company_query(value: str | None) -> str:
    """Normalize user-entered ticker or company text for matching only.

    Punctuation, corporate suffixes, and repeated whitespace are removed from
    the comparison key. The original company name remains untouched in the
    returned suggestion so official display metadata is preserved.
    """
    normalized = _CORPORATE_SUFFIXES.sub(" ", str(value or "").casefold())
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _load_index(loader: Callable[[], list[dict]] | None = None) -> tuple[dict[str, str], ...]:
    """Load a short-lived index from the shared supported screener universe."""
    global _INDEX
    now = time.monotonic()
    with _INDEX_LOCK:
        if _INDEX is not None and now - _INDEX[0] < _CACHE_TTL_SECONDS:
            return _INDEX[1]
        rows = (loader or screener.get_screener_results)()
        index = tuple(
            {
                "symbol": str(row.get("symbol") or "").upper().strip(),
                "name": str(row.get("name") or row.get("symbol") or "").strip(),
            }
            for row in rows
            if str(row.get("symbol") or "").strip()
            and str(row.get("name") or row.get("symbol") or "").strip()
        )
        _INDEX = (now, index)
        return index


def search_companies(
    query: str | None,
    *,
    limit: int = _MAX_RESULTS,
    loader: Callable[[], list[dict]] | None = None,
) -> list[CompanySuggestion]:
    """Return deterministically ranked supported-company suggestions.

    Args:
        query: Raw ticker or company-name text from the Analyze input.
        limit: Maximum number of suggestions to return, capped at eight.
        loader: Optional index loader used by tests or another approved adapter.

    Returns:
        Suggestions ordered by exact ticker, ticker prefix, exact name, name
        prefix, word prefix, then controlled fuzzy matching. Empty input,
        malformed input, and unavailable search data return an empty list.

    Raises:
        OSError: Propagated when the shared universe cannot be read; the UI
            adapter converts this failure to a non-blocking status message.
    """
    normalized = normalize_company_query(query)
    if not normalized:
        return []
    limit = max(1, min(int(limit), _MAX_RESULTS))
    ticker_query = re.sub(r"[^a-z0-9]", "", str(query or "").casefold())
    results: list[CompanySuggestion] = []
    for row in _load_index(loader):
        symbol = row["symbol"]
        name = row["name"]
        ticker_key = re.sub(r"[^a-z0-9]", "", symbol.casefold())
        name_key = normalize_company_query(name)
        name_words = name_key.split()
        if ticker_query and ticker_key == ticker_query:
            bucket = 0
        elif ticker_query and ticker_key.startswith(ticker_query):
            bucket = 1
        elif name_key == normalized:
            bucket = 2
        elif name_key.startswith(normalized):
            bucket = 3
        elif any(word.startswith(normalized) for word in name_words):
            bucket = 4
        elif len(normalized) >= 3 and (
            normalized in name_key
            or difflib.SequenceMatcher(None, normalized, name_key).ratio() >= 0.72
        ):
            bucket = 5
        else:
            continue
        results.append(CompanySuggestion(symbol, name, (bucket, len(name), symbol)))
    results.sort(key=lambda item: item.rank)
    return results[:limit]


def clear_company_search_cache() -> None:
    """Clear the process-local index after a supported-universe refresh."""
    global _INDEX
    with _INDEX_LOCK:
        _INDEX = None
