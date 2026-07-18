"""Framework-neutral projections and envelopes for the public API contract."""

from __future__ import annotations

import math
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as Base64Error
from typing import Any

from codes.api.errors import from_code
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
    return from_code(code, request_id, message=message, details=details)


def pagination(
    page: int,
    page_size: int,
    total_items: int,
    *,
    next_cursor: str | None = None,
    previous_cursor: str | None = None,
) -> Pagination:
    result: Pagination = {
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": math.ceil(total_items / page_size) if total_items else 0,
    }
    if next_cursor is not None:
        result["next_cursor"] = next_cursor
    if previous_cursor is not None:
        result["previous_cursor"] = previous_cursor
    return result


def encode_cursor(offset: int) -> str:
    """Encode a non-negative result offset as an opaque URL-safe cursor."""
    if offset < 0:
        raise ValueError("cursor offset must be non-negative")
    return urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> int:
    """Decode and validate an opaque cursor, rejecting malformed input."""
    if not cursor or len(cursor) > 32:
        raise ValueError("cursor is invalid")
    try:
        decoded = urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("ascii")
        offset = int(decoded)
    except (ValueError, UnicodeDecodeError, Base64Error) as error:
        raise ValueError("cursor is invalid") from error
    if offset < 0:
        raise ValueError("cursor is invalid")
    return offset


def collection_response(
    data: list[object], page: int, page_size: int, total_items: int, request_id: str,
    *, next_cursor: str | None = None, previous_cursor: str | None = None,
    errors: list[dict[str, object]] | None = None,
) -> CollectionResponse:
    result: CollectionResponse = {
        "data": data,
        "pagination": pagination(
            page, page_size, total_items, next_cursor=next_cursor, previous_cursor=previous_cursor
        ),
        "meta": meta(request_id),
    }
    if errors:
        result["partial"] = True
        result["errors"] = errors
    return result


def partial_data_response(
    data: object, request_id: str, errors: list[dict[str, object]]
) -> DataResponse:
    """Return successful data plus independently failed optional sections."""
    return {"data": data, "meta": meta(request_id), "partial": True, "errors": errors}


def screener_resource(raw: dict[str, Any]) -> ScreenerResource:
    return DomainScreenerResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]


def portfolio_summary(raw: dict[str, Any]) -> PortfolioSummary:
    return DomainPortfolioResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]


def account_resource(raw: dict[str, Any]) -> AccountResource:
    return UserResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]


def billing_resource(raw: dict[str, Any]) -> BillingResource:
    return SubscriptionResponse.from_mapping(raw).to_dict()  # type: ignore[return-value]
