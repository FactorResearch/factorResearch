"""Backend composition root for process-wide volatile dependencies."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from codes.core.ports import Clock, IdGenerator


class SystemClock:
    """Production clock adapter."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.perf_counter()


class UuidGenerator:
    """Production opaque-ID adapter."""

    def new_id(self) -> str:
        return uuid.uuid4().hex


@dataclass(frozen=True)
class RuntimeDependencies:
    """Small container passed only where a volatile dependency is required."""

    clock: Clock
    ids: IdGenerator


def compose_runtime(
    *, clock: Clock | None = None, ids: IdGenerator | None = None
) -> RuntimeDependencies:
    """Build production dependencies while allowing deterministic test adapters."""

    return RuntimeDependencies(clock=clock or SystemClock(), ids=ids or UuidGenerator())
