"""Transport-safe API error and partial-response projections."""

from __future__ import annotations

from typing import Any, Mapping

from codes.api.schemas import ErrorDetail
from codes.core.errors import error_for_code


def from_code(
    code: str,
    request_id: str,
    *,
    message: str | None = None,
    details: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Build a stable API error without exposing raw exception text.

    The central error registry owns category, severity, retryability, and safe
    default copy. The API keeps its v1 three-field error shape for compatibility
    and places correlation in the shared ``meta.request_id`` field.
    """
    structured = error_for_code(code, details=details)
    payload: ErrorDetail = {
        "code": structured.code,
        "message": message or structured.definition.message,
        "retryable": structured.definition.retryable,
    }
    if details:
        payload["details"] = dict(details)
    return {"error": payload, "meta": {"api_version": "v1", "request_id": request_id}}
