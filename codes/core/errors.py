"""Stable error semantics shared by domain services and delivery adapters.

This module owns classification, recovery guidance, safe user copy, and the
small partial-response envelope. It deliberately does not render HTTP or UI
components; those adapters consume :class:`StructuredError` and preserve the
same machine-readable behavior across channels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, Mapping, TypeVar


class ErrorCategory(StrEnum):
    """Stable categories used for recovery, analytics, and customer support."""

    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RATE_LIMITED = "rate_limited"
    DEPENDENCY = "dependency"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    INTERNAL = "internal"
    PARTIAL = "partial"


class ErrorSeverity(StrEnum):
    """Customer-impact severity independent of HTTP status."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RecoveryAction(StrEnum):
    """Safe next action that a delivery adapter may present to a user."""

    NONE = "none"
    FIX_INPUT = "fix_input"
    SIGN_IN = "sign_in"
    RETRY = "retry"
    REFRESH = "refresh"
    CONTACT_SUPPORT = "contact_support"


@dataclass(frozen=True)
class ErrorDefinition:
    """Registry entry defining public semantics for one error code."""

    code: str
    category: ErrorCategory
    message: str
    severity: ErrorSeverity
    retryable: bool
    recovery: RecoveryAction
    status: int


ERROR_REGISTRY: Mapping[str, ErrorDefinition] = {
    "invalid_request": ErrorDefinition("invalid_request", ErrorCategory.VALIDATION, "The request could not be understood.", ErrorSeverity.WARNING, False, RecoveryAction.FIX_INPUT, 400),
    "unauthorized": ErrorDefinition("unauthorized", ErrorCategory.AUTHENTICATION, "Authentication is required.", ErrorSeverity.WARNING, False, RecoveryAction.SIGN_IN, 401),
    "forbidden": ErrorDefinition("forbidden", ErrorCategory.AUTHORIZATION, "You do not have access to this resource.", ErrorSeverity.WARNING, False, RecoveryAction.CONTACT_SUPPORT, 403),
    "not_found": ErrorDefinition("not_found", ErrorCategory.NOT_FOUND, "The requested resource was not found.", ErrorSeverity.INFO, False, RecoveryAction.NONE, 404),
    "rate_limited": ErrorDefinition("rate_limited", ErrorCategory.RATE_LIMITED, "Too many requests. Try again shortly.", ErrorSeverity.WARNING, True, RecoveryAction.RETRY, 429),
    "dependency_unavailable": ErrorDefinition("dependency_unavailable", ErrorCategory.DEPENDENCY, "A required service is temporarily unavailable.", ErrorSeverity.ERROR, True, RecoveryAction.RETRY, 503),
    "timeout": ErrorDefinition("timeout", ErrorCategory.TIMEOUT, "The request took too long to complete.", ErrorSeverity.WARNING, True, RecoveryAction.RETRY, 504),
    "cancelled": ErrorDefinition("cancelled", ErrorCategory.CANCELLED, "The operation was cancelled.", ErrorSeverity.INFO, False, RecoveryAction.NONE, 409),
    "partial_response": ErrorDefinition("partial_response", ErrorCategory.PARTIAL, "Some results are unavailable, but the available results are shown.", ErrorSeverity.WARNING, True, RecoveryAction.REFRESH, 206),
    "internal_error": ErrorDefinition("internal_error", ErrorCategory.INTERNAL, "Something went wrong. Please try again.", ErrorSeverity.CRITICAL, False, RecoveryAction.CONTACT_SUPPORT, 500),
}


@dataclass(frozen=True)
class StructuredError:
    """Safe, serializable failure semantics with no raw exception text."""

    definition: ErrorDefinition
    details: Mapping[str, Any] = field(default_factory=dict)
    error_id: str | None = None

    @property
    def code(self) -> str:
        """Return the stable registry code."""
        return self.definition.code

    def to_dict(self) -> dict[str, Any]:
        """Return an adapter-safe representation for API or UI delivery."""
        result: dict[str, Any] = {
            "code": self.code,
            "category": self.definition.category.value,
            "message": self.definition.message,
            "severity": self.definition.severity.value,
            "retryable": self.definition.retryable,
            "recovery": self.definition.recovery.value,
        }
        if self.error_id:
            result["error_id"] = self.error_id
        if self.details:
            result["details"] = dict(self.details)
        return result


class ClassifiedError(Exception):
    """Application exception carrying an explicit public error code.

    Services may raise this exception when they already know the appropriate
    stable code. The original message remains diagnostic only and is never
    copied into a user-facing response.
    """

    def __init__(self, code: str, *, details: Mapping[str, Any] | None = None) -> None:
        if code not in ERROR_REGISTRY:
            raise ValueError(f"unknown error code: {code}")
        super().__init__(code)
        self.code = code
        self.details = dict(details or {})


def error_for_code(code: str, *, details: Mapping[str, Any] | None = None) -> StructuredError:
    """Build a registered error, rejecting unregistered public codes."""
    definition = ERROR_REGISTRY.get(code, ERROR_REGISTRY["internal_error"])
    return StructuredError(definition, details or {})


def classify_exception(error: BaseException) -> StructuredError:
    """Map an exception to bounded recovery semantics without leaking details.

    Explicit ``failure_class`` values from existing workers are supported for
    compatibility. Unknown exceptions become ``internal_error``; callers may
    log the traceback separately, but must deliver only this safe result.
    """
    if isinstance(error, ClassifiedError):
        return error_for_code(error.code, details=error.details)
    failure_class = str(getattr(error, "failure_class", "")).lower()
    if failure_class in {"permission", "authorization"}:
        return error_for_code("forbidden")
    if failure_class in {"validation", "invalid_request"} or isinstance(error, ValueError):
        return error_for_code("invalid_request")
    if failure_class in {"not_found", "missing"} or isinstance(error, KeyError):
        return error_for_code("not_found")
    if failure_class in {"timeout", "timed_out"} or isinstance(error, TimeoutError):
        return error_for_code("timeout")
    if failure_class in {"cancelled", "canceled"}:
        return error_for_code("cancelled")
    if failure_class in {"dependency", "provider", "transient"}:
        return error_for_code("dependency_unavailable")
    if failure_class == "partial":
        return error_for_code("partial_response")
    return error_for_code("internal_error")


T = TypeVar("T")


@dataclass(frozen=True)
class PartialResponse(Generic[T]):
    """Represent successful data alongside independently failed sections."""

    data: T
    failures: tuple[StructuredError, ...] = ()

    @property
    def partial(self) -> bool:
        """Return whether one or more optional sections failed."""
        return bool(self.failures)

    def to_dict(self) -> dict[str, Any]:
        """Return a stable envelope that never includes exception text."""
        return {
            "data": self.data,
            "partial": self.partial,
            "errors": [failure.to_dict() for failure in self.failures],
        }
