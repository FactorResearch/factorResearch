"""Framework-neutral projections and envelopes for the public API contract."""

from __future__ import annotations

import math
from typing import Any

from codes.api.schemas import (
    AccountResource,
    AnalysisResource,
    ApiMeta,
    BillingResource,
    CollectionResponse,
    DataResponse,
    ErrorResponse,
    Pagination,
    PortfolioSummary,
    ScreenerResource,
)
from codes.domain.responses import (
    AnalysisResponse as DomainAnalysisResponse,
)
from codes.domain.responses import (
    ErrorResponse as DomainErrorResponse,
)
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


def error_response(code: str, message: str, request_id: str) -> ErrorResponse:
    error = DomainErrorResponse(code, message)
    return {
        "error": error.to_dict(),
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


def analysis_resource(raw: dict[str, Any], symbol: str) -> AnalysisResource:
    return DomainAnalysisResponse.from_mapping(raw, symbol).to_dict()  # type: ignore[return-value]


def screener_resource(raw: dict[str, Any]) -> ScreenerResource:
    return DomainScreenerResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]


def portfolio_summary(raw: dict[str, Any]) -> PortfolioSummary:
    return DomainPortfolioResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]


def account_resource(raw: dict[str, Any]) -> AccountResource:
    return UserResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]


def billing_resource(raw: dict[str, Any]) -> BillingResource:
    return SubscriptionResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]


def _number_or_none(value: object) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _number_or_zero(value: object) -> float | int:
    return _number_or_none(value) or 0


def _string_or_none(value: object) -> str | None:
    return str(value) if value is not None else None
