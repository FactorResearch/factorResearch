"""Application boundary for account profile and account-owned data workflows."""

from __future__ import annotations

from codes import auth
from codes.data import analytics_db, db
from codes.services import billing_service, permissions, portfolio_service, user_settings
from codes.domain.responses import PortfolioResponse, SubscriptionResponse, UserResponse


def display_name(user_id: str) -> str:
    persona = auth.get_dev_persona()
    if persona:
        label = str(persona.get("label") or "there").strip()
        return label.split("/")[0].strip()
    raw = str(user_id or "").strip().split("@", 1)[0]
    parts = [part for chunk in raw.split("_") for part in chunk.split("-") if part]
    return " ".join(parts[:2]).title() if parts else "there"


def auth_provider() -> str:
    persona = auth.get_dev_persona()
    return auth.AUTH_PROVIDER or ("developer session" if persona else "session")


def portfolio_summaries(user_id: str) -> list[dict]:
    return [response.to_dict() for response in portfolio_responses(user_id)]


def portfolio_responses(user_id: str) -> list[PortfolioResponse]:
    return [
        PortfolioResponse.from_mapping(
            {
                "name": name,
                "holdings": len(
                    (portfolio_service.load_portfolio(user_id, name) or {}).get("holdings", {})
                ),
            }
        )
        for name in (portfolio_service.list_portfolios(user_id) or [])
    ]


def subscription_summary(user_id: str) -> dict:
    subscription = permissions.get_or_create_subscription(user_id)
    paid = billing_service.user_has_paid(user_id)
    return SubscriptionResponse.from_mapping(
        {
            "plan": str(subscription.get("plan") or "free"),
            "status": str(subscription.get("status") or "trialing"),
            "trial_usage": permissions.get_trial_analysis_usage(user_id),
            "paid": paid,
        }
    ).to_dict()


def billing_entry_url(user_id: str) -> str:
    """Return the web navigation target separately from subscription semantics."""
    if billing_service.user_has_paid(user_id):
        return "/billing/portal"
    return billing_service.get_entry_url(source="profile", feature="subscription")


def subscription_response(user_id: str) -> SubscriptionResponse:
    return SubscriptionResponse.from_mapping(subscription_summary(user_id))


def user_response(user_id: str) -> UserResponse:
    return UserResponse.from_mapping(
        {
            "display_name": display_name(user_id),
            "auth_provider": auth_provider(),
            "settings": get_settings(user_id),
        }
    )


def get_settings(user_id: str) -> dict:
    return user_settings.get_user_settings(user_id)


def normalize_settings(settings: dict | None) -> dict:
    return user_settings.normalize_user_settings(settings)


def update_settings(user_id: str, patch: dict) -> dict:
    return user_settings.update_user_settings(user_id, patch)


def save_preferences(user_id: str, *, theme: str, notifications: list[str]) -> dict:
    user_settings.set_notifications(user_id, notifications)
    return user_settings.update_user_settings(user_id, {"appearance": {"theme": theme}})


def add_saved_screener(user_id: str, **values) -> dict:
    return user_settings.add_saved_screener(user_id, **values)


def delete_saved_screener(user_id: str, screener_id: str) -> dict:
    return user_settings.delete_saved_screener(user_id, screener_id)


def delete_account_data(user_id: str) -> dict:
    """Own the transaction-shaped account deletion workflow for every adapter."""
    from codes.services.analysis_snapshot_service import delete_user_snapshots

    summary = portfolio_service.delete_all_user_data(user_id)
    summary["database_records"] = db.delete_user_records(user_id)
    summary["analytics_events"] = analytics_db.delete_identity_events(user_id)
    summary["custom_snapshots"] = delete_user_snapshots(user_id)
    return summary
