"""Framework-neutral entry points used by billing presentation adapters."""

from __future__ import annotations

from codes import billing


def get_entry_url(plan: str = "premium", **context: str | None) -> str:
    return billing.get_billing_entry_url(plan=plan, **context)


def user_has_paid(user_id: str) -> bool:
    return billing.user_has_paid(user_id)
