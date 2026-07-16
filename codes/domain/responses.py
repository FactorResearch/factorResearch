"""Immutable, framework-neutral response models for application use cases.

These models contain data and machine-readable semantics only.  Delivery adapters
own formatting, CSS classes, component selection, layout, links, and HTTP envelopes.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]

_PRESENTATION_KEYS = frozenset(
    {
        "badge",
        "class",
        "class_name",
        "classname",
        "color",
        "component",
        "css_class",
        "icon",
        "layout",
        "style",
        "verdict_label",
    }
)
_FACTOR_KEYS = (
    "graham",
    "quality",
    "momentum",
    "piotroski",
    "altman",
    "risk",
    "greenblatt",
    "buffett",
    "earnings_revision",
    "profitability",
    "fcf_quality",
    "capital_allocation",
    "growth_quality",
    "regime",
    "insider_activity",
    "factor_momentum",
    "alternative_data",
    "spy_benchmark",
    "bias",
    "comomentum",
    "market_fear",
)


def _finite_number(value: object) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _number_or_zero(value: object) -> float | int:
    return _finite_number(value) or 0


def _string_or_none(value: object) -> str | None:
    return str(value) if value is not None else None


def _semantic_copy(value: object) -> JsonValue:
    """Copy JSON-shaped data while removing delivery and presentation hints."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {
            str(key): _semantic_copy(item)
            for key, item in value.items()
            if str(key).lower() not in _PRESENTATION_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_semantic_copy(item) for item in value]
    return str(value)


def _immutable_mapping(value: Mapping[str, Any] | None) -> Mapping[str, JsonValue]:
    copied = _semantic_copy(value or {})
    assert isinstance(copied, dict)
    return MappingProxyType(copied)


def _factor_score(metrics: Mapping[str, Any]) -> float | int | None:
    for key in (
        "composite_score",
        "total_score",
        "score",
        "f_score",
        "z_score",
        "fcf_quality_score",
        "capital_allocation_score",
        "growth_quality_score",
        "profitability_score",
        "factor_momentum_score",
        "alternative_data_score",
        "market_fear_score",
    ):
        number = _finite_number(metrics.get(key))
        if number is not None:
            return number
    return None


def _factor_status(metrics: Mapping[str, Any]) -> str:
    for key in ("status", "signal", "verdict", "regime", "zone_label", "label", "grade"):
        value = metrics.get(key)
        if value not in (None, ""):
            return str(value).upper().replace(" ", "_")
    return "AVAILABLE" if metrics else "UNAVAILABLE"


@dataclass(frozen=True)
class FactorResponse:
    key: str
    score: float | int | None
    status: str
    metrics: Mapping[str, JsonValue] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_mapping(cls, key: str, raw: Mapping[str, Any] | None) -> FactorResponse:
        metrics = _immutable_mapping(raw)
        return cls(
            key=key, score=_factor_score(metrics), status=_factor_status(metrics), metrics=metrics
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "key": self.key,
            "score": self.score,
            "status": self.status,
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True)
class CapabilityResponse:
    key: str
    available: bool
    reason_code: str | None = None

    def to_dict(self) -> dict[str, JsonValue]:
        return {"key": self.key, "available": self.available, "reason_code": self.reason_code}


@dataclass(frozen=True)
class AnalysisResponse:
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
    factors: tuple[FactorResponse, ...]
    capabilities: tuple[CapabilityResponse, ...]
    _details: Mapping[str, JsonValue] = field(repr=False, compare=False)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], symbol: str = "") -> AnalysisResponse:
        enhanced = raw.get("enhanced") or raw.get("composite") or {}
        if not isinstance(enhanced, Mapping):
            enhanced = {}
        normalized_symbol = str(raw.get("symbol") or raw.get("ticker") or symbol).upper()
        factors = tuple(
            FactorResponse.from_mapping(key, value if isinstance(value, Mapping) else None)
            for key in _FACTOR_KEYS
            if (value := raw.get(key)) is not None
        )
        secondary = str(raw.get("secondary_status") or "complete").lower()
        capabilities = (
            CapabilityResponse("summary", True),
            CapabilityResponse(
                "factor_details", bool(factors), None if factors else "NOT_AVAILABLE"
            ),
            CapabilityResponse(
                "historical_charts",
                bool(raw.get("price_history") or raw.get("spy_history")),
                None if raw.get("price_history") or raw.get("spy_history") else "NOT_AVAILABLE",
            ),
            CapabilityResponse(
                "secondary_signals",
                secondary == "complete",
                None if secondary == "complete" else secondary.upper(),
            ),
        )
        return cls(
            symbol=normalized_symbol,
            company_name=str(raw.get("company_name") or raw.get("name") or normalized_symbol),
            sector=str(raw.get("sector") or ""),
            market_code=str(raw.get("market_code") or "US").upper(),
            price=_finite_number(raw.get("price")),
            market_cap=_finite_number(raw.get("market_cap")),
            composite_score=_finite_number(enhanced.get("composite_score")),
            verdict=str(enhanced.get("verdict") or "PENDING"),
            analysis_version=str(raw.get("analysis_version") or ""),
            generated_at=_string_or_none(raw.get("generated_at")),
            factors=factors,
            capabilities=capabilities,
            _details=_immutable_mapping(raw),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "sector": self.sector,
            "market_code": self.market_code,
            "price": self.price,
            "market_cap": self.market_cap,
            "composite_score": self.composite_score,
            "verdict": self.verdict,
            "analysis_version": self.analysis_version,
            "generated_at": self.generated_at,
            "factors": [factor.to_dict() for factor in self.factors],
            "capabilities": [capability.to_dict() for capability in self.capabilities],
        }

    def presentation_data(self) -> dict[str, JsonValue]:
        """Return semantic data in the legacy shape expected by the Dash renderer."""
        data = dict(self._details)
        data.update(
            {
                "symbol": self.symbol,
                "name": self.company_name,
                "sector": self.sector,
                "market_code": self.market_code,
                "price": self.price,
                "market_cap": self.market_cap,
                "analysis_version": self.analysis_version,
                "generated_at": self.generated_at,
            }
        )
        data.pop("verdict_label", None)
        return data

    def __getitem__(self, key: str) -> JsonValue:
        """Support read-only legacy adapter access during incremental migration."""
        return self.presentation_data()[key]

    def get(self, key: str, default: JsonValue = None) -> JsonValue:
        return self.presentation_data().get(key, default)


@dataclass(frozen=True)
class ScreenerResponse:
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
    _details: Mapping[str, JsonValue] = field(repr=False, compare=False)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ScreenerResponse:
        return cls(
            symbol=str(raw.get("symbol") or "").upper(),
            name=str(raw.get("name") or raw.get("symbol") or ""),
            sector=str(raw.get("sector") or ""),
            market_code=str(raw.get("market_code") or "US").upper(),
            composite_score=_number_or_zero(raw.get("composite_score")),
            verdict=str(raw.get("verdict") or "NOT_ANALYZED"),
            price=_finite_number(raw.get("price")),
            market_cap=_finite_number(raw.get("market_cap")),
            analyzed=bool(raw.get("analyzed")),
            updated_at=_string_or_none(raw.get("updated_at")),
            _details=_immutable_mapping(raw),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "sector": self.sector,
            "market_code": self.market_code,
            "composite_score": self.composite_score,
            "verdict": self.verdict,
            "price": self.price,
            "market_cap": self.market_cap,
            "analyzed": self.analyzed,
            "updated_at": self.updated_at,
        }

    def presentation_data(self) -> dict[str, JsonValue]:
        data = dict(self._details)
        data.update(self.to_dict())
        return data


@dataclass(frozen=True)
class PortfolioResponse:
    name: str
    holdings: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> PortfolioResponse:
        return cls(name=str(raw.get("name") or ""), holdings=max(0, int(raw.get("holdings") or 0)))

    def to_dict(self) -> dict[str, JsonValue]:
        return {"name": self.name, "holdings": self.holdings}


@dataclass(frozen=True)
class UserResponse:
    display_name: str
    auth_provider: str
    settings: Mapping[str, JsonValue]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> UserResponse:
        settings = raw.get("settings") if isinstance(raw.get("settings"), Mapping) else {}
        appearance = (
            settings.get("appearance") if isinstance(settings.get("appearance"), Mapping) else {}
        )
        notifications = (
            settings.get("notifications")
            if isinstance(settings.get("notifications"), Mapping)
            else {}
        )
        safe_settings = {
            "appearance": {"theme": str(appearance.get("theme") or "system")},
            "notifications": {
                "product_updates": bool(notifications.get("product_updates")),
                "research_digest": bool(notifications.get("research_digest")),
                "security_alerts": bool(notifications.get("security_alerts")),
            },
        }
        return cls(
            display_name=str(raw.get("display_name") or ""),
            auth_provider=str(raw.get("auth_provider") or "session"),
            settings=_immutable_mapping(safe_settings),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "display_name": self.display_name,
            "auth_provider": self.auth_provider,
            "settings": dict(self.settings),
        }


@dataclass(frozen=True)
class SubscriptionResponse:
    plan: str
    status: str
    trial_usage: int
    paid: bool

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SubscriptionResponse:
        return cls(
            plan=str(raw.get("plan") or "free"),
            status=str(raw.get("status") or "trialing"),
            trial_usage=max(0, int(raw.get("trial_usage") or 0)),
            paid=bool(raw.get("paid")),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "plan": self.plan,
            "status": self.status,
            "trial_usage": self.trial_usage,
            "paid": self.paid,
        }


@dataclass(frozen=True)
class JobResponse:
    status: str
    queued: int | None
    processing: int | None
    failed: int | None

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "status": self.status,
            "queued": self.queued,
            "processing": self.processing,
            "failed": self.failed,
        }


@dataclass(frozen=True)
class ErrorResponse:
    code: str
    message: str
    retryable: bool = False

    def to_dict(self) -> dict[str, JsonValue]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}
