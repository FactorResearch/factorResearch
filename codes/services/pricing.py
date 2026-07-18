"""Canonical pricing tiers and their server-side entitlements."""

from __future__ import annotations

FREE = "free"
PREMIUM = "premium"

PLANS = {
    FREE: {
        "analysis_limit": 3,
        "features": ["analysis", "custom_weights"],
        "stripe_price_env": None,
        "display_name": "Free",
        "display_price": "$0",
        "display_subtitle": "Start free",
        "display_features": ["3 company analyses", "Custom factor weights"],
    },
    PREMIUM: {
        "analysis_limit": None,
        "features": ["analysis", "custom_weights", "backtest", "portfolio_analytics"],
        "stripe_price_env": "STRIPE_PREMIUM_PRICE_ID",
        "display_name": "Premium",
        "display_price": "$29",
        "display_subtitle": "Per month",
        "display_features": [
            "Unlimited company analysis",
            "Historical backtesting",
            "Portfolio analytics and simulations",
            "Strategy validation workflow",
        ],
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


def plan_catalog() -> list[dict[str, object]]:
    """Return ordered, allow-listed display metadata for the pricing surface."""
    catalog: list[dict[str, object]] = []
    for plan in (FREE, PREMIUM):
        definition = PLANS[plan]
        catalog.append(
            {
                "key": plan,
                "name": definition["display_name"],
                "price": definition["display_price"],
                "subtitle": definition["display_subtitle"],
                "features": list(definition["display_features"]),
            }
        )
    return catalog


def plan_for_price_id(price_id: str | None, configured_price_ids: dict[str, str | None]) -> str:
    """Resolve a provider price to a plan, failing closed for unknown prices."""
    if not price_id:
        return FREE
    for plan, configured in configured_price_ids.items():
        if configured and configured == price_id and plan in PLANS:
            return plan
    return FREE
