from unittest.mock import Mock, patch

from codes.app_modules.company_identity import company_logo
from codes.services import company_logo_cache


def test_company_logo_uses_same_origin_cache_route(monkeypatch):
    monkeypatch.setenv("LOGO_DEV_PUBLISHABLE_KEY", "pk_test")

    component = company_logo("BRK.B", "Berkshire Hathaway")

    assert component.src.startswith("/company-logo?")
    assert "token=" not in component.src
    assert "symbol=BRK.B" in component.src


def test_cache_hit_does_not_fetch_provider():
    cached = {"image_bytes": b"cached", "mime_type": "image/png"}
    with patch.object(company_logo_cache.db, "get_company_logo", return_value=cached), \
         patch.object(company_logo_cache, "_fetch") as fetch:
        result = company_logo_cache.get_or_fetch_logo("AAPL", "Apple Inc.")

    assert result is cached
    fetch.assert_not_called()


def test_cache_miss_fetches_and_persists():
    with patch.object(company_logo_cache.db, "get_company_logo", return_value=None), \
         patch.object(company_logo_cache, "_fetch", return_value=(b"png", "image/png")), \
         patch.object(company_logo_cache.db, "upsert_company_logo") as upsert:
        result = company_logo_cache.get_or_fetch_logo("AAPL", "Apple Inc.")

    assert result["image_bytes"] == b"png"
    assert result["mime_type"] == "image/png"
    upsert.assert_called_once()


def test_fetch_rejects_oversized_image(monkeypatch):
    monkeypatch.setenv("LOGO_DEV_PUBLISHABLE_KEY", "pk_test")
    response = Mock()
    response.headers.get_content_type.return_value = "image/png"
    response.read.return_value = b"x" * (company_logo_cache._MAX_IMAGE_BYTES + 1)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)

    with patch.object(company_logo_cache, "urlopen", return_value=response):
        assert company_logo_cache._fetch("Apple Inc.") is None
