"""Typed shapes generated from and checked against the public v1 contract.

These types describe transport payloads only.  Domain response models remain a
separate concern; API adapters deliberately project service results into these
stable, allow-listed fields.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class ApiMeta(TypedDict):
    api_version: str
    request_id: str


class Pagination(TypedDict):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class ErrorDetail(TypedDict):
    code: str
    message: str
    retryable: bool


class ErrorResponse(TypedDict):
    error: ErrorDetail
    meta: ApiMeta


class AnalysisResource(TypedDict):
    symbol: str
    company_name: str
    sector: str
    market_code: str
    price: float | int | None
    market_cap: float | int | None
    composite_score: float | int | None
    verdict: str
    analysis_version: str
    generated_at: str | None
    factors: list[FactorResource]
    capabilities: list[CapabilityResource]


class FactorResource(TypedDict):
    key: str
    score: float | int | None
    status: str
    metrics: dict[str, object]


class CapabilityResource(TypedDict):
    key: str
    available: bool
    reason_code: str | None


class ScreenerResource(TypedDict):
    symbol: str
    name: str
    sector: str
    market_code: str
    composite_score: float | int
    verdict: str
    price: float | int | None
    market_cap: float | int | None
    analyzed: bool
    updated_at: str | None


class PortfolioSummary(TypedDict):
    id: NotRequired[str]
    name: str
    holdings: int
    created_at: NotRequired[str]
    updated_at: NotRequired[str | None]
    version: NotRequired[int]
    deleted_at: NotRequired[str | None]


class SyncMetadata(TypedDict):
    created_at: str
    updated_at: str
    version: int
    deleted_at: str | None


class AppearanceSettings(TypedDict):
    theme: str


class NotificationSettings(TypedDict):
    product_updates: bool
    research_digest: bool
    security_alerts: bool


class AccountSettings(TypedDict):
    appearance: AppearanceSettings
    notifications: NotificationSettings
    _sync: NotRequired[SyncMetadata]


class AccountResource(TypedDict):
    display_name: str
    auth_provider: str
    settings: AccountSettings


class BillingResource(TypedDict):
    plan: str
    status: str
    trial_usage: int
    paid: bool


class DataResponse(TypedDict):
    data: object
    meta: ApiMeta


class CollectionResponse(TypedDict):
    data: list[object]
    pagination: Pagination
    meta: ApiMeta
