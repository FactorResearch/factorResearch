"""Canonical pricing tiers and their server-side entitlements."""

from __future__ import annotations

FREE = "free"
PREMIUM = "premium"

PLANS = {
    FREE: {
        "analysis_limit": 3,
        "features": ["analysis", "custom_weights"],
    },
    PREMIUM: {
        "analysis_limit": None,
        "features": ["analysis", "custom_weights", "backtest", "portfolio_analytics"],
    },
}


def normalize_plan(plan: str | None) -> str:
    """Map legacy and unknown plan records to the free tier."""
    return PREMIUM if str(plan or FREE).lower() == PREMIUM else FREE
