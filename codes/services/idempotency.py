"""Shared idempotency claims and deterministic command replay."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable, Protocol

from codes.data import db


class IdempotencyConflict(ValueError):
    """The same key was reused for a different command payload."""


class IdempotencyInProgress(RuntimeError):
    """An equivalent command is currently being processed by another request."""


@dataclass(frozen=True)
class IdempotencyResult:
    """Original or newly produced command result."""

    response: Any
    status_code: int = 200
    replayed: bool = False


class IdempotencyStore(Protocol):
    """Persistence contract for atomic claims and terminal outcomes."""

    def claim(self, user_id: str, key: str, operation: str, request_hash: str) -> dict[str, Any]: ...

    def complete(self, user_id: str, key: str, request_hash: str, response: Any, status_code: int) -> None: ...

    def fail(self, user_id: str, key: str, request_hash: str, response: Any, status_code: int) -> None: ...


class DatabaseIdempotencyStore:
    """PostgreSQL-backed store using the user-state migration table."""

    def claim(self, user_id: str, key: str, operation: str, request_hash: str) -> dict[str, Any]:
        return db.claim_idempotency(user_id, key, operation, request_hash)

    def complete(self, user_id: str, key: str, request_hash: str, response: Any, status_code: int) -> None:
        db.complete_idempotency(user_id, key, request_hash, response, status_code)

    def fail(self, user_id: str, key: str, request_hash: str, response: Any, status_code: int) -> None:
        db.fail_idempotency(user_id, key, request_hash, response, status_code)


class InMemoryIdempotencyStore:
    """Deterministic test/development store with atomic process-local claims."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], dict[str, Any]] = {}
        self._lock = Lock()

    def claim(self, user_id: str, key: str, operation: str, request_hash: str) -> dict[str, Any]:
        with self._lock:
            record = self._records.get((user_id, key))
            if record is None:
                record = {
                    "user_id": user_id, "idempotency_key": key, "operation": operation,
                    "request_hash": request_hash, "status": "processing",
                    "response_json": None, "response_status": None,
                }
                self._records[(user_id, key)] = record
            return dict(record)

    def complete(self, user_id: str, key: str, request_hash: str, response: Any, status_code: int) -> None:
        with self._lock:
            record = self._records[(user_id, key)]
            record.update(status="completed", response_json=response, response_status=status_code)

    def fail(self, user_id: str, key: str, request_hash: str, response: Any, status_code: int) -> None:
        with self._lock:
            record = self._records[(user_id, key)]
            record.update(status="failed", response_json=response, response_status=status_code)


class IdempotencyService:
    """Execute one command at most once and replay its durable outcome."""

    def __init__(self, store: IdempotencyStore) -> None:
        self._store = store

    def execute(
        self,
        *,
        user_id: str,
        key: str,
        operation: str,
        payload: Any,
        handler: Callable[[], Any],
        status_code: int = 200,
    ) -> IdempotencyResult:
        """Claim, execute, persist, and replay a command outcome."""
        normalized_key = _validate_key(key)
        if not user_id:
            raise ValueError("user_id is required for idempotency")
        request_hash = _hash_payload(operation, payload)
        record = self._store.claim(user_id, normalized_key, operation, request_hash)
        if record.get("request_hash") != request_hash:
            raise IdempotencyConflict("idempotency key was reused with a different request")
        if record.get("status") in {"completed", "failed"}:
            return IdempotencyResult(record.get("response_json"), int(record.get("response_status") or 200), True)
        if record.get("status") != "processing":
            raise IdempotencyInProgress("idempotency claim is in an unknown state")
        try:
            response = handler()
        except Exception as error:
            failure = {"error": "command_failed", "type": type(error).__name__}
            self._store.fail(user_id, normalized_key, request_hash, failure, 500)
            raise
        self._store.complete(user_id, normalized_key, request_hash, response, status_code)
        return IdempotencyResult(response, status_code, False)


def _validate_key(key: str) -> str:
    normalized = str(key or "").strip()
    if not normalized or len(normalized) > 255 or any(ord(char) < 33 or ord(char) > 126 for char in normalized):
        raise ValueError("Idempotency-Key must be a printable value of 1-255 characters")
    return normalized


def _hash_payload(operation: str, payload: Any) -> str:
    encoded = json.dumps({"operation": operation, "payload": payload}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


idempotency = IdempotencyService(DatabaseIdempotencyStore())
