from __future__ import annotations

from codes.core.errors import (
    ClassifiedError,
    ErrorCategory,
    PartialResponse,
    RecoveryAction,
    classify_exception,
    error_for_code,
)


def test_registry_maps_temporary_dependency_failure_to_bounded_retry() -> None:
    result = classify_exception(RuntimeError("provider secret must not escape"))
    assert result.code == "internal_error"
    assert result.definition.category == ErrorCategory.INTERNAL
    assert not result.definition.retryable
    assert "provider secret" not in str(result.to_dict())


def test_explicit_failure_class_maps_to_safe_dependency_copy() -> None:
    error = RuntimeError("raw provider response")
    error.failure_class = "dependency"  # type: ignore[attr-defined]
    result = classify_exception(error)
    assert result.code == "dependency_unavailable"
    assert result.definition.retryable
    assert result.definition.recovery == RecoveryAction.RETRY
    assert result.to_dict()["message"] == "A required service is temporarily unavailable."


def test_classified_error_preserves_safe_details_only() -> None:
    result = classify_exception(ClassifiedError("invalid_request", details={"field": "page"}))
    assert result.to_dict()["details"] == {"field": "page"}
    assert result.definition.category == ErrorCategory.VALIDATION


def test_partial_response_preserves_success_and_structured_failures() -> None:
    response = PartialResponse(
        {"history": [1, 2]},
        (error_for_code("dependency_unavailable", details={"section": "forecast"}),),
    )
    assert response.partial
    assert response.to_dict()["data"] == {"history": [1, 2]}
    assert response.to_dict()["errors"][0]["code"] == "dependency_unavailable"
