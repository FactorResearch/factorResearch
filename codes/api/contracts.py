"""Framework-neutral projections and envelopes for the public API contract."""

from __future__ import annotations

import math
from typing import Any

from codes.api.schemas import (
    AccountResource,
    ApiMeta,
    BillingResource,
    CollectionResponse,
    DataResponse,
    ErrorResponse,
    Pagination,
    PortfolioSummary,
    ScreenerResource,
)
from codes.core.errors import error_for_code
from codes.domain.responses import (
    PortfolioResponse as DomainPortfolioResponse,
)
from codes.domain.responses import (
    ScreenerResponse as DomainScreenerResponse,
)
from codes.domain.responses import (
    SubscriptionResponse,
    UserResponse,
)

API_VERSION = "v1"
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def meta(request_id: str) -> ApiMeta:
    return {"api_version": API_VERSION, "request_id": request_id}


def data_response(data: object, request_id: str) -> DataResponse:
    return {"data": data, "meta": meta(request_id)}


def error_response(
    code: str,
    message: str | None,
    request_id: str,
    *,
    details: dict[str, object] | None = None,
) -> ErrorResponse:
    """Build the stable error envelope using the central error registry.

    ``message`` is retained as a compatibility override for existing callers,
    while the registry remains authoritative for category, severity, retry,
    recovery, and safe default copy.
    """
    structured = error_for_code(code, details=details)
    payload = {
        "code": structured.code,
        "message": message or structured.definition.message,
        "retryable": structured.definition.retryable,
    }
    return {
        "error": payload,
        "meta": meta(request_id),
    }


def pagination(page: int, page_size: int, total_items: int) -> Pagination:
    return {
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": math.ceil(total_items / page_size) if total_items else 0,
    }


def collection_response(
    data: list[object], page: int, page_size: int, total_items: int, request_id: str
) -> CollectionResponse:
    return {
        "data": data,
        "pagination": pagination(page, page_size, total_items),
        "meta": meta(request_id),
    }


def screener_resource(raw: dict[str, Any]) -> ScreenerResource:
    return DomainScreenerResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]


def portfolio_summary(raw: dict[str, Any]) -> PortfolioSummary:
    return DomainPortfolioResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]


def account_resource(raw: dict[str, Any]) -> AccountResource:
    return UserResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]


def billing_resource(raw: dict[str, Any]) -> BillingResource:
    return SubscriptionResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]
