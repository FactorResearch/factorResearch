"""Shared runtime configuration access for the application process."""

from pathlib import Path

from codes.services.configuration import ConfigurationService, build_default_configuration_service

_SERVICE = build_default_configuration_service()


def configuration_service() -> ConfigurationService:
    """Return the process-wide validated configuration service."""
    return _SERVICE


def get_config(name: str) -> object:
    """Return one typed setting through the central configuration boundary."""
    return _SERVICE.get(name)


def is_production() -> bool:
    return str(get_config("FLASK_ENV")).lower() == "production"


def cache_root() -> Path:
    configured = get_config("APP_CACHE_DIR")
    return Path(configured).expanduser().resolve() if configured else Path(__file__).resolve().parents[2] / ".cache"
