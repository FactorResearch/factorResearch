"""Fail-closed validation for production configuration without printing secrets."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from cryptography.fernet import Fernet

from codes.core.database_roles import is_market_worker_process


def _present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def validate_production_environment() -> list[str]:
    """Return sanitized production configuration contract failures.

    The migration release role has an additional credential boundary: it must
    receive dedicated market/users URLs that are absent from normal runtime
    processes. Values are compared but never included in returned messages.
    """
    errors: list[str] = []
    process_role = os.environ.get("PROCESS_ROLE", "").strip().lower()
    market_worker = is_market_worker_process(process_role)
    required = [
        "FLASK_SECRET_KEY",
        "ENCRYPTION_KEY",
        "TRUSTED_HOSTS",
        "REDIS_URL",
        "SEC_USER_AGENT",
    ]
    if market_worker:
        required.append("DATABASE_MARKET_WORKER_URL")
    else:
        required.extend(("DATABASE_MARKET_URL", "DATABASE_USERS_URL"))
    if process_role not in {"migration"} and not market_worker:
        required.append("DATABASE_USERS_SERVICE_URL")
    errors.extend(f"{name} is required" for name in required if not _present(name))
    errors.extend(_secret_and_transport_errors())
    errors.extend(_migration_process_errors())
    errors.extend(_authentication_errors())
    errors.extend(_service_policy_errors())
    return errors


def _secret_and_transport_errors() -> list[str]:
    """Return sanitized secret, host, database, and Redis validation failures."""
    errors: list[str] = []

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

    errors.extend(_database_transport_errors())
    if _present("REDIS_URL") and urlparse(os.environ["REDIS_URL"]).scheme != "rediss":
        errors.append("REDIS_URL must use TLS (rediss)")
    return errors


def _database_transport_errors() -> list[str]:
    """Return sanitized database URL, separation, and exposure failures.

    Returns:
        Configuration messages containing environment names only. Parsed
        usernames, hosts, passwords, and complete URLs are never returned.
    """

    errors: list[str] = []
    if _present("DATABASE_MARKET_URL") and os.environ.get("DATABASE_MARKET_URL") == os.environ.get(
        "DATABASE_USERS_URL"
    ):
        errors.append("DATABASE_MARKET_URL and DATABASE_USERS_URL must be isolated")
    database_urls = (
        "DATABASE_MARKET_URL",
        "DATABASE_MARKET_WORKER_URL",
        "DATABASE_USERS_URL",
        "DATABASE_USERS_SERVICE_URL",
    )
    for name in database_urls:
        if _present(name) and urlparse(os.environ[name]).scheme not in {"postgres", "postgresql"}:
            errors.append(f"{name} must be a PostgreSQL URL")
    errors.extend(
        _distinct_database_role_errors(
            "DATABASE_USERS_URL",
            "DATABASE_USERS_SERVICE_URL",
        )
    )
    errors.extend(
        _distinct_database_role_errors(
            "DATABASE_MARKET_URL",
            "DATABASE_MARKET_WORKER_URL",
        )
    )
    if is_market_worker_process(os.environ.get("PROCESS_ROLE")):
        for name in (
            "DATABASE_USERS_URL",
            "DATABASE_USERS_SERVICE_URL",
            "DATABASE_MIGRATION_MARKET_URL",
            "DATABASE_MIGRATION_USERS_URL",
            "DATABASE_MIGRATION_ANALYTICS_URL",
        ):
            if _present(name):
                errors.append(f"{name} must not be available to market workers")
    return errors


def _distinct_database_role_errors(primary_name: str, secondary_name: str) -> list[str]:
    """Reject two workload URLs that reuse one PostgreSQL login identity.

    Args:
        primary_name: Environment name for the first workload URL.
        secondary_name: Environment name for the separated workload URL.

    Returns:
        One sanitized error when URLs or parsed usernames overlap; otherwise an
        empty list. Credential values and usernames are never returned.
    """

    if not (_present(primary_name) and _present(secondary_name)):
        return []
    primary = os.environ[primary_name]
    secondary = os.environ[secondary_name]
    primary_role = urlparse(primary).username
    secondary_role = urlparse(secondary).username
    if primary == secondary or (primary_role is not None and primary_role == secondary_role):
        return [f"{secondary_name} must use a PostgreSQL role distinct from {primary_name}"]
    return []


def _authentication_errors() -> list[str]:
    """Return provider-specific authentication configuration failures."""
    errors: list[str] = []
    provider = os.environ.get("AUTH_PROVIDER", "").strip().lower()
    auth_requirements = {
        "auth0": ("AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET"),
        "clerk": ("CLERK_PUBLIC_KEY", "CLERK_ISSUER", "CLERK_AUDIENCE"),
        "supabase": ("SUPABASE_URL", "SUPABASE_API_KEY"),
    }
    if provider not in auth_requirements:
        errors.append("AUTH_PROVIDER must be auth0, clerk, or supabase")
    else:
        errors.extend(f"{name} is required for {provider}" for name in auth_requirements[provider] if not _present(name))
    return errors


def _service_policy_errors() -> list[str]:
    """Return public URL, identity, billing, and unsafe release-flag failures."""
    errors: list[str] = []
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
    if os.environ.get("PORTFOLIO_STORAGE_BACKEND", "").strip().lower() == "cache":
        errors.append("PORTFOLIO_STORAGE_BACKEND cannot use cache in production")
    return errors


def _migration_process_errors() -> list[str]:
    """Return sanitized release-role credential separation failures."""
    if os.environ.get("PROCESS_ROLE", "").strip().lower() != "migration":
        return []
    pairs = [
        ("DATABASE_MIGRATION_MARKET_URL", "DATABASE_MARKET_URL"),
        ("DATABASE_MIGRATION_USERS_URL", "DATABASE_USERS_URL"),
    ]
    analytics_runtime_url = (
        os.environ.get("DATABASE_ANALYTICS_URL")
        or os.environ.get("ANALYTICS_DATABASE_URL")
        or os.environ.get("FACTORRESEARCH_ANALYTICS_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
    )
    if analytics_runtime_url and analytics_runtime_url != os.environ.get("DATABASE_MARKET_URL"):
        pairs.append(("DATABASE_MIGRATION_ANALYTICS_URL", "DATABASE_ANALYTICS_URL"))

    errors: list[str] = []
    for migration_name, runtime_name in pairs:
        if not _present(migration_name):
            errors.append(f"{migration_name} is required for the migration process")
            continue
        if urlparse(os.environ[migration_name]).scheme not in {"postgres", "postgresql"}:
            errors.append(f"{migration_name} must be a PostgreSQL URL")
        migration_url = os.environ[migration_name]
        runtime_url = (
            analytics_runtime_url
            if runtime_name == "DATABASE_ANALYTICS_URL"
            else os.environ.get(runtime_name, "")
        )
        migration_role = urlparse(migration_url).username
        runtime_role = urlparse(runtime_url).username
        if migration_url == runtime_url or (
            migration_role is not None and migration_role == runtime_role
        ):
            errors.append(f"{migration_name} must differ from {runtime_name}")
    return errors
