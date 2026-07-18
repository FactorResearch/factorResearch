"""Thread- and async-safe request correlation context propagation."""

from __future__ import annotations

import contextvars
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Iterator


@dataclass(frozen=True)
class RequestContext:
    """Identifiers for one request and its nested operations."""

    request_id: str
    correlation_id: str
    operation_id: str
    parent_operation_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        request_id: str | None = None,
        correlation_id: str | None = None,
        parent_operation_id: str | None = None,
    ) -> "RequestContext":
        """Create a root context or child operation with opaque identifiers."""
        request = request_id or _new_id("req")
        correlation = correlation_id or request
        return cls(request, correlation, _new_id("op"), parent_operation_id)

    def child(self) -> "RequestContext":
        """Create a nested operation while preserving request correlation."""
        return replace(self, operation_id=_new_id("op"), parent_operation_id=self.operation_id)


_current: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar(
    "request_context", default=None
)


def current_context() -> RequestContext | None:
    """Return the context local to the current thread/task, if any."""
    return _current.get()


def capture_context() -> RequestContext | None:
    """Return the immutable context to pass across a worker boundary."""
    return _current.get()


def bind_context(context: RequestContext) -> contextvars.Token[RequestContext | None]:
    """Bind a context and return the token required for exact restoration."""
    return _current.set(context)


def reset_context(token: contextvars.Token[RequestContext | None]) -> None:
    """Restore the context value that existed before a request or job scope."""
    _current.reset(token)


@contextmanager
def context_scope(context: RequestContext | None) -> Iterator[RequestContext | None]:
    """Bind a context for a scope and always restore the previous value."""
    token = _current.set(context)
    try:
        yield context
    finally:
        _current.reset(token)


def child_operation() -> RequestContext:
    """Bind and return a child operation, or create a standalone context."""
    context = _current.get()
    child = context.child() if context else RequestContext.create()
    _current.set(child)
    return child


class ContextFilter:
    """Logging filter that enriches records without logging user content."""

    def filter(self, record: object) -> bool:
        context = current_context()
        record.request_id = context.request_id if context else ""
        record.correlation_id = context.correlation_id if context else ""
        record.operation_id = context.operation_id if context else ""
        return True


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"
