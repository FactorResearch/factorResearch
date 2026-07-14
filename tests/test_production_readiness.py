from cryptography.fernet import Fernet

from codes.core.production_readiness import validate_production_environment


BASE = {
    "FLASK_SECRET_KEY": "session-secret-with-at-least-32-characters",
    "ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "TRUSTED_HOSTS": "research.example",
    "DATABASE_MARKET_URL": "postgresql://market",
    "DATABASE_USERS_URL": "postgresql://users",
    "REDIS_URL": "rediss://redis",
    "SEC_USER_AGENT": "FactorResearch ops@research.example",
    "AUTH_PROVIDER": "auth0",
    "AUTH0_DOMAIN": "auth.research.example",
    "AUTH0_CLIENT_ID": "client",
    "AUTH0_CLIENT_SECRET": "secret",
    "PUBLIC_BASE_URL": "https://research.example",
    "APP_FEATURE_FLAG": "V1",
}


def _configure(monkeypatch):
    for name, value in BASE.items():
        monkeypatch.setenv(name, value)
    for name in ("DISABLE_CSRF_DEV", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)


def test_valid_production_configuration_passes(monkeypatch):
    _configure(monkeypatch)
    assert validate_production_environment() == []


def test_preflight_rejects_shared_databases_and_insecure_url(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setenv("DATABASE_USERS_URL", BASE["DATABASE_MARKET_URL"])
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://research.example")
    failures = validate_production_environment()
    assert any("must be isolated" in failure for failure in failures)
    assert any("must use HTTPS" in failure for failure in failures)


def test_preflight_rejects_incomplete_auth_and_unsafe_flags(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.delenv("AUTH0_CLIENT_SECRET")
    monkeypatch.setenv("APP_FEATURE_FLAG", "INTERNAL")
    monkeypatch.setenv("DISABLE_CSRF_DEV", "true")
    failures = validate_production_environment()
    assert any("AUTH0_CLIENT_SECRET" in failure for failure in failures)
    assert any("public production tier" in failure for failure in failures)
    assert any("cannot be enabled" in failure for failure in failures)


def test_preflight_requires_clerk_claim_context(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setenv("AUTH_PROVIDER", "clerk")
    monkeypatch.setenv("CLERK_PUBLIC_KEY", "public-key")
    monkeypatch.delenv("CLERK_ISSUER", raising=False)
    monkeypatch.delenv("CLERK_AUDIENCE", raising=False)

    failures = validate_production_environment()

    assert any("CLERK_ISSUER" in failure for failure in failures)
    assert any("CLERK_AUDIENCE" in failure for failure in failures)


def test_preflight_rejects_weak_crypto_hosts_and_transport(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setenv("FLASK_SECRET_KEY", "short")
    monkeypatch.setenv("ENCRYPTION_KEY", "invalid")
    monkeypatch.setenv("TRUSTED_HOSTS", "*")
    monkeypatch.setenv("REDIS_URL", "redis://redis")
    failures = validate_production_environment()
    assert any("at least 32" in failure for failure in failures)
    assert any("valid Fernet" in failure for failure in failures)
    assert any("explicit hostnames" in failure for failure in failures)
    assert any("must use TLS" in failure for failure in failures)
