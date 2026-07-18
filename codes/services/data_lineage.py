"""Shared freshness and provenance metadata for cached and persisted datasets.

This application-layer module defines the small, JSON-safe contract shared by
cache envelopes, analysis results, and user-facing trust panels. It does not
fetch providers or decide whether a financial value is valid; provider
adapters and domain validators retain those responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class FreshnessState(StrEnum):
    """Observable freshness states used by cache and presentation layers."""

    CURRENT = "current"
    STALE = "stale"
    EXPIRED = "expired"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class LineageMetadata:
    """Describe where a dataset came from and whether it remains usable.

    ``source_timestamp`` is the provider's observation or filing timestamp;
    ``acquired_at`` is when Cenvarn obtained the payload. ``freshness_ttl`` is
    optional because filing-aware datasets are invalidated by a newer filing,
    not by wall-clock age. The metadata is descriptive and never substitutes
    for domain-level validation.
    """

    source: str
    acquired_at: str
    source_timestamp: str | None
    freshness_policy: str
    freshness_state: FreshnessState
    freshness_ttl_seconds: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation for persistence."""
        return {
            "source": self.source,
            "acquired_at": self.acquired_at,
            "source_timestamp": self.source_timestamp,
            "freshness_policy": self.freshness_policy,
            "freshness_state": self.freshness_state.value,
            "freshness_ttl_seconds": self.freshness_ttl_seconds,
        }


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO timestamp, treating date-only values as UTC midnight."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC)


def freshness_state(
    acquired_at: str | None,
    *,
    now: datetime | None = None,
    ttl_seconds: int | None = None,
) -> FreshnessState:
    """Classify cache age without silently treating unknown data as current.

    A value is ``stale`` after one TTL and ``expired`` after two TTLs. If no
    acquisition timestamp or policy is available, freshness is unavailable;
    callers may still display the value with that limitation visible.
    """
    acquired = _parse_timestamp(acquired_at)
    if acquired is None or ttl_seconds is None or ttl_seconds <= 0:
        return FreshnessState.UNAVAILABLE
    reference = now or datetime.now(UTC)
    age = max(0.0, (reference - acquired).total_seconds())
    if age >= ttl_seconds * 2:
        return FreshnessState.EXPIRED
    if age >= ttl_seconds:
        return FreshnessState.STALE
    return FreshnessState.CURRENT


def build_lineage(
    *,
    source: str,
    acquired_at: str | None = None,
    source_timestamp: str | None = None,
    freshness_policy: str = "not-configured",
    freshness_ttl_seconds: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build persisted lineage metadata for a dataset or cache envelope.

    ``source`` must identify a provider, database, or explicit user input;
    ``source_timestamp`` remains nullable when a provider does not expose it.
    The returned mapping is safe to embed in JSON and preserves unknown
    freshness instead of inventing a current value.
    """
    acquired = acquired_at or (now or datetime.now(UTC)).isoformat()
    return LineageMetadata(
        source=source,
        acquired_at=acquired,
        source_timestamp=source_timestamp,
        freshness_policy=freshness_policy,
        freshness_state=freshness_state(acquired, now=now, ttl_seconds=freshness_ttl_seconds),
        freshness_ttl_seconds=freshness_ttl_seconds,
    ).as_dict()
