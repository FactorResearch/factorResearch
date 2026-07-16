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

API_VERSION = "v1"
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def meta(request_id: str) -> ApiMeta:
    return {"api_version": API_VERSION, "request_id": request_id}


def data_response(data: object, request_id: str) -> DataResponse:
    return {"data": data, "meta": meta(request_id)}


def error_response(code: str, message: str, request_id: str) -> ErrorResponse:
    return {
        "error": {"code": code, "message": message},
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
    composite = raw.get("enhanced") or raw.get("composite") or {}
    return {
        "symbol": str(raw.get("symbol") or raw.get("ticker") or symbol).upper(),
        "company_name": str(raw.get("company_name") or raw.get("name") or symbol),
        "sector": str(raw.get("sector") or ""),
        "market_code": str(raw.get("market_code") or "US").upper(),
        "price": _number_or_none(raw.get("price")),
        "market_cap": _number_or_none(raw.get("market_cap")),
        "composite_score": _number_or_none(composite.get("composite_score")),
        "verdict": str(composite.get("verdict") or "PENDING"),
        "analysis_version": str(raw.get("analysis_version") or ""),
        "generated_at": _string_or_none(raw.get("generated_at")),
    }


def screener_resource(raw: dict[str, Any]) -> ScreenerResource:
    return {
        "symbol": str(raw.get("symbol") or "").upper(),
        "name": str(raw.get("name") or raw.get("symbol") or ""),
        "sector": str(raw.get("sector") or ""),
        "market_code": str(raw.get("market_code") or "US").upper(),
        "composite_score": _number_or_zero(raw.get("composite_score")),
        "verdict": str(raw.get("verdict") or "NOT_ANALYZED"),
        "price": _number_or_none(raw.get("price")),
        "market_cap": _number_or_none(raw.get("market_cap")),
        "analyzed": bool(raw.get("analyzed")),
        "updated_at": _string_or_none(raw.get("updated_at")),
    }


def portfolio_summary(raw: dict[str, Any]) -> PortfolioSummary:
    return {
        "name": str(raw.get("name") or ""),
        "holdings": max(0, int(raw.get("holdings") or 0)),
    }


def account_resource(raw: dict[str, Any]) -> AccountResource:
    settings = dict(raw.get("settings") or {})
    appearance = dict(settings.get("appearance") or {})
    notifications = dict(settings.get("notifications") or {})
    return {
        "display_name": str(raw.get("display_name") or ""),
        "auth_provider": str(raw.get("auth_provider") or "session"),
        "settings": {
            "appearance": {"theme": str(appearance.get("theme") or "system")},
            "notifications": {
                "product_updates": bool(notifications.get("product_updates")),
                "research_digest": bool(notifications.get("research_digest")),
                "security_alerts": bool(notifications.get("security_alerts")),
            },
        },
    }


def billing_resource(raw: dict[str, Any]) -> BillingResource:
    return {
        "plan": str(raw.get("plan") or "free"),
        "status": str(raw.get("status") or "trialing"),
        "trial_usage": max(0, int(raw.get("trial_usage") or 0)),
        "paid": bool(raw.get("paid")),
    }


def _number_or_none(value: object) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _number_or_zero(value: object) -> float | int:
    return _number_or_none(value) or 0


def _string_or_none(value: object) -> str | None:
    return str(value) if value is not None else None
