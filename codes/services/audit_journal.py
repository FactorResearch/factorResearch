"""Append-only, searchable operational event journal with secret redaction."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Mapping
from uuid import uuid4

_DEFAULT_PATH = Path(os.environ.get("AUDIT_LOG_PATH", "/tmp/cenvarn-audit-events.jsonl"))
_SENSITIVE_KEY = re.compile(r"password|token|secret|api[_-]?key|credential|authorization|cookie", re.I)
_MAX_DETAIL_DEPTH = 8


class AuditJournal:
    """Write immutable JSONL events and provide bounded field-based search."""

    def __init__(self, path: Path = _DEFAULT_PATH, *, retention_days: int = 90) -> None:
        if retention_days < 1:
            raise ValueError("retention_days must be positive")
        self._path = path
        self._retention_days = retention_days
        self._lock = RLock()

    def record(
        self,
        event_type: str,
        *,
        action: str = "",
        actor_id: str = "",
        user_id: str = "",
        request_id: str = "",
        correlation_id: str = "",
        job_id: str = "",
        ticker: str = "",
        provider: str = "",
        component: str = "",
        severity: str = "INFO",
        outcome: str = "success",
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append one redacted event; identifiers are bounded and non-secret."""
        event = {
            "event_id": f"evt-{uuid4().hex}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": _bounded(event_type),
            "action": _bounded(action),
            "actor_id": _bounded(actor_id),
            "user_id": _bounded(user_id),
            "request_id": _bounded(request_id),
            "correlation_id": _bounded(correlation_id or request_id),
            "job_id": _bounded(job_id),
            "ticker": _bounded(ticker).upper(),
            "provider": _bounded(provider),
            "component": _bounded(component),
            "severity": _bounded(severity).upper(),
            "outcome": _bounded(outcome),
            "details": _redact(dict(details or {})),
        }
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
        return event

    def search(
        self,
        *,
        user_id: str | None = None,
        ticker: str | None = None,
        provider: str | None = None,
        job_id: str | None = None,
        component: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> tuple[dict[str, Any], ...]:
        """Search committed events without exposing mutable journal state."""
        if not 1 <= limit <= 1_000:
            raise ValueError("limit must be between 1 and 1000")
        filters = {
            "user_id": user_id,
            "ticker": ticker.upper() if ticker else None,
            "provider": provider,
            "job_id": job_id,
            "component": component,
            "severity": severity.upper() if severity else None,
        }
        matches: list[dict[str, Any]] = []
        with self._lock:
            try:
                lines = self._path.read_text(encoding="utf-8").splitlines()
            except OSError:
                return ()
        for line in reversed(lines):
            try:
                event = json.loads(line)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if all(value is None or event.get(key) == value for key, value in filters.items()):
                matches.append(event)
                if len(matches) == limit:
                    break
        return tuple(matches)


def _bounded(value: Any) -> str:
    return str(value or "")[:256]


def _redact(value: Any, depth: int = 0) -> Any:
    if depth >= _MAX_DETAIL_DEPTH:
        return "[TRUNCATED]"
    if isinstance(value, Mapping):
        return {
            str(key)[:128]: "[REDACTED]" if _SENSITIVE_KEY.search(str(key)) else _redact(item, depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, depth + 1) for item in value[:100]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value if not isinstance(value, str) else value[:2_000]
    return str(value)[:256]


audit_journal = AuditJournal()
