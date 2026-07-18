"""Canonical pricing tiers and their server-side entitlements."""

from __future__ import annotations

FREE = "free"
PREMIUM = "premium"

PLANS = {
    FREE: {
        "analysis_limit": 3,
        "features": ["analysis", "custom_weights"],
        "stripe_price_env": None,
    },
    PREMIUM: {
        "analysis_limit": None,
        "features": ["analysis", "custom_weights", "backtest", "portfolio_analytics"],
        "stripe_price_env": "STRIPE_PREMIUM_PRICE_ID",
    },
}


def normalize_plan(plan: str | None) -> str:
    """Map legacy and unknown plan records to the free tier."""
    return PREMIUM if str(plan or FREE).lower() == PREMIUM else FREE


def plan_definition(plan: str | None) -> dict[str, object] | None:
    """Return the allow-listed plan definition for billing integrations."""
    normalized = str(plan or FREE).strip().lower()
    definition = PLANS.get(normalized)
    return dict(definition) if isinstance(definition, dict) else None


def plan_for_price_id(price_id: str | None, configured_price_ids: dict[str, str | None]) -> str:
    """Resolve a provider price to a plan, failing closed for unknown prices."""
    if not price_id:
        return FREE
    for plan, configured in configured_price_ids.items():
        if configured and configured == price_id and plan in PLANS:
            return plan
    return FREE
