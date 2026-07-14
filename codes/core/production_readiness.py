"""Fail-closed validation for production configuration without printing secrets."""

from __future__ import annotations

import os
from urllib.parse import urlparse
from cryptography.fernet import Fernet


def _present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def validate_production_environment() -> list[str]:
    errors = []
    required = (
        "FLASK_SECRET_KEY",
        "ENCRYPTION_KEY",
        "TRUSTED_HOSTS",
        "DATABASE_MARKET_URL",
        "DATABASE_USERS_URL",
        "REDIS_URL",
        "SEC_USER_AGENT",
    )
    errors.extend(f"{name} is required" for name in required if not _present(name))

    if _present("FLASK_SECRET_KEY") and len(os.environ["FLASK_SECRET_KEY"]) < 32:
        errors.append("FLASK_SECRET_KEY must be at least 32 characters")
    if _present("ENCRYPTION_KEY"):
        try:
            Fernet(os.environ["ENCRYPTION_KEY"].encode())
        except (TypeError, ValueError):
            errors.append("ENCRYPTION_KEY must be a valid Fernet key")
    trusted_hosts = [host.strip() for host in os.environ.get("TRUSTED_HOSTS", "").split(",") if host.strip()]
    if any(host == "*" or "/" in host or "://" in host for host in trusted_hosts):
        errors.append("TRUSTED_HOSTS must contain explicit hostnames")

    if _present("DATABASE_MARKET_URL") and os.environ.get("DATABASE_MARKET_URL") == os.environ.get("DATABASE_USERS_URL"):
        errors.append("DATABASE_MARKET_URL and DATABASE_USERS_URL must be isolated")
    for name in ("DATABASE_MARKET_URL", "DATABASE_USERS_URL"):
        if _present(name) and urlparse(os.environ[name]).scheme not in {"postgres", "postgresql"}:
            errors.append(f"{name} must be a PostgreSQL URL")
    if _present("REDIS_URL") and urlparse(os.environ["REDIS_URL"]).scheme != "rediss":
        errors.append("REDIS_URL must use TLS (rediss)")

    provider = os.environ.get("AUTH_PROVIDER", "").strip().lower()
    auth_requirements = {
        "auth0": ("AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET"),
        "clerk": ("CLERK_PUBLIC_KEY",),
        "supabase": ("SUPABASE_URL", "SUPABASE_API_KEY"),
    }
    if provider not in auth_requirements:
        errors.append("AUTH_PROVIDER must be auth0, clerk, or supabase")
    else:
        errors.extend(f"{name} is required for {provider}" for name in auth_requirements[provider] if not _present(name))

    base_url = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("APP_BASE_URL", "")
    if not base_url or urlparse(base_url).scheme != "https":
        errors.append("PUBLIC_BASE_URL or APP_BASE_URL must use HTTPS")

    sec_identity = os.environ.get("SEC_USER_AGENT", "").lower()
    if "example.com" in sec_identity or "contact@example" in sec_identity:
        errors.append("SEC_USER_AGENT must contain a monitored production identity")

    stripe_values = ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET")
    if any(_present(name) for name in stripe_values) and not all(_present(name) for name in stripe_values):
        errors.append("Stripe secret and webhook secret must be configured together")

    if os.environ.get("APP_FEATURE_FLAG", "").upper() in {"INTERNAL", "BETA"}:
        errors.append("APP_FEATURE_FLAG must be a public production tier")
    if os.environ.get("DISABLE_CSRF_DEV", "").lower() in {"1", "true", "yes"}:
        errors.append("DISABLE_CSRF_DEV cannot be enabled in production")
    return errors
