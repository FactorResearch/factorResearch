"""Centralized feature permissions and trial usage accounting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from codes import auth
from codes.data import db


TRIAL_ANALYSIS_LIMIT = 3
TRIAL_PORTFOLIO_SIM_LIMIT = 1
ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing", "past_due"}
PAID_PLANS = {"premium", "professional"}


class Feature(str, Enum):
    ANALYSIS = "analysis"
    CUSTOM_WEIGHTS = "custom_weights"
    SCREENING = "screening"
    BACKTEST = "backtest"
    PORTFOLIO_ANALYTICS = "portfolio_analytics"
    EXPORT = "export"


@dataclass(frozen=True)
class PermissionResult:
    allowed: bool
    feature: Feature
    reason: str = ""
    plan: str = "trial"
    status: str = "trialing"
    remaining: int | None = None
    upgrade_required: bool = False

    @property
    def message(self) -> str:
        if self.allowed:
            if self.remaining is not None:
                return f"{self.remaining} / {TRIAL_ANALYSIS_LIMIT} free analyses remaining"
            return ""
        if self.reason:
            return self.reason
        return "This feature requires Premium."


def normalize_feature(feature: Feature | str) -> Feature:
    if isinstance(feature, Feature):
        return feature
    return Feature(str(feature))


def get_or_create_subscription(user_id: str) -> dict[str, Any]:
    override = auth.get_dev_subscription_override()
    if override and override.get("user_id") == user_id:
        return override
    sub = db.get_subscription(user_id)
    if sub:
        return sub
    return db.upsert_subscription(user_id, plan="trial", status="trialing")


def is_paid_subscription(subscription: dict[str, Any] | None) -> bool:
    if not subscription:
        return False
    plan = str(subscription.get("plan") or "trial").lower()
    status = str(subscription.get("status") or "").lower()
    return plan in PAID_PLANS and status in ACTIVE_SUBSCRIPTION_STATUSES


def get_trial_analysis_usage(user_id: str) -> int:
    return get_feature_usage_total(user_id, Feature.ANALYSIS)


def get_feature_usage_total(user_id: str, feature: Feature | str) -> int:
    feature = normalize_feature(feature)
    if hasattr(db, "get_total_usage"):
        return int(db.get_total_usage(user_id, feature.value) or 0)
    usage = db.get_usage(user_id, feature.value)
    return int(usage.get("usage_count") or 0)


def can_access_feature(user_id: str, feature: Feature | str) -> PermissionResult:
    feature = normalize_feature(feature)
    subscription = get_or_create_subscription(user_id)
    plan = str(subscription.get("plan") or "trial").lower()
    status = str(subscription.get("status") or "trialing").lower()

    if is_paid_subscription(subscription):
        return PermissionResult(True, feature, plan=plan, status=status)

    if feature == Feature.CUSTOM_WEIGHTS:
        return PermissionResult(True, feature, plan=plan, status=status)

    if feature == Feature.ANALYSIS:
        used = get_feature_usage_total(user_id, feature)
        remaining = max(TRIAL_ANALYSIS_LIMIT - used, 0)
        if remaining > 0:
            return PermissionResult(
                True,
                feature,
                plan=plan,
                status=status,
                remaining=remaining,
            )
        return PermissionResult(
            False,
            feature,
            reason=(
                "You have used your 3 free analyses. Unlock Factor Research Premium "
                "for unlimited company analysis, custom strategies, historical "
                "backtesting, portfolio analytics, and strategy tracking."
            ),
            plan=plan,
            status=status,
            remaining=0,
            upgrade_required=True,
        )

    if feature == Feature.PORTFOLIO_ANALYTICS:
        used = get_feature_usage_total(user_id, feature)
        remaining = max(TRIAL_PORTFOLIO_SIM_LIMIT - used, 0)
        if remaining > 0:
            return PermissionResult(
                True,
                feature,
                plan=plan,
                status=status,
                remaining=remaining,
            )
        return PermissionResult(
            False,
            feature,
            reason=(
                "You have used your free portfolio simulation. Unlock Factor Research Premium "
                "for unlimited portfolio analytics, simulations, and strategy backtesting."
            ),
            plan=plan,
            status=status,
            remaining=0,
            upgrade_required=True,
        )

    messages = {
        Feature.BACKTEST: "Historical backtesting requires Premium.",
        Feature.SCREENING: "Unlimited screening requires Premium.",
        Feature.EXPORT: "Research data export requires Premium.",
    }
    return PermissionResult(
        False,
        feature,
        reason=messages.get(feature, "This feature requires Premium."),
        plan=plan,
        status=status,
        upgrade_required=True,
    )


def record_feature_usage(user_id: str, feature: Feature | str, usage_key: str | None = None) -> dict:
    feature = normalize_feature(feature)
    return db.increment_usage(user_id, feature.value, usage_key=usage_key)


def consume_analysis_if_allowed(user_id: str, ticker: str | None = None) -> PermissionResult:
    result = can_access_feature(user_id, Feature.ANALYSIS)
    if result.allowed and result.remaining is not None:
        record_feature_usage(user_id, Feature.ANALYSIS, usage_key=ticker or Feature.ANALYSIS.value)
        used = get_trial_analysis_usage(user_id)
        remaining = max(TRIAL_ANALYSIS_LIMIT - used, 0)
        return PermissionResult(
            True,
            Feature.ANALYSIS,
            plan=result.plan,
            status=result.status,
            remaining=remaining,
        )
    return result
