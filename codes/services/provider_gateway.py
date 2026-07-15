"""Bounded, deduplicated provider calls with timeouts and circuit breakers."""

from __future__ import annotations

import concurrent.futures
import os
import threading
import time
from collections.abc import Callable

from codes.core import singleflight

_FAILURE_THRESHOLD = int(os.environ.get("PROVIDER_CIRCUIT_FAILURES", "3"))
_RECOVERY_SECONDS = int(os.environ.get("PROVIDER_CIRCUIT_RECOVERY_SECONDS", "60"))
_DEFAULT_TIMEOUT = float(os.environ.get("PROVIDER_TIMEOUT_SECONDS", "8"))
_states: dict[str, dict] = {}
_semaphores: dict[str, threading.BoundedSemaphore] = {}
_guard = threading.Lock()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=16, thread_name_prefix="provider-gateway")


def _state(provider: str) -> tuple[dict, threading.BoundedSemaphore]:
    with _guard:
        state = _states.setdefault(provider, {"failures": 0, "opened_at": 0.0})
        limit = int(os.environ.get(f"PROVIDER_{provider.upper()}_CONCURRENCY", "4"))
        semaphore = _semaphores.setdefault(provider, threading.BoundedSemaphore(max(limit, 1)))
    return state, semaphore


def call(provider: str, operation: str, callback: Callable, *, default=None, timeout: float | None = None):
    state, semaphore = _state(provider)
    now = time.monotonic()
    wait_seconds = timeout or _DEFAULT_TIMEOUT
    with _guard:
        if state["failures"] >= _FAILURE_THRESHOLD and now - state["opened_at"] < _RECOVERY_SECONDS:
            return default

    def execute():
        def invoke():
            if not semaphore.acquire(timeout=wait_seconds):
                raise TimeoutError(f"{provider} concurrency limit")
            try:
                return callback()
            finally:
                semaphore.release()

        return _executor.submit(invoke).result(timeout=wait_seconds)

    try:
        result = singleflight.run(f"provider:{provider}:{operation}", execute, timeout=max(int(wait_seconds), 1))
        with _guard:
            state.update(failures=0, opened_at=0.0)
        return result
    except Exception as exc:
        with _guard:
            state["failures"] += 1
            if state["failures"] >= _FAILURE_THRESHOLD:
                state["opened_at"] = time.monotonic()
        print(f"{provider} {operation} failed: {exc}")
        return default


def health() -> dict:
    with _guard:
        return {name: dict(state) for name, state in _states.items()}
