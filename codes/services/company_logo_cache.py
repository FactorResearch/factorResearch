"""Bounded, database-backed cache for provider-hosted company logos."""

import datetime
import hashlib
import os
from urllib.parse import quote
from urllib.request import Request, urlopen

from codes.data import db

_CACHE_DAYS = 30
_MAX_IMAGE_BYTES = 512 * 1024
_ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}


def provider_key(symbol: str, company_name: str) -> str:
    identity = f"logo.dev|{symbol.strip().upper()}|{company_name.strip().casefold()}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _provider_url(company_name: str) -> str | None:
    token = os.environ.get("LOGO_DEV_PUBLISHABLE_KEY", "").strip()
    if not token:
        return None
    return (
        f"https://img.logo.dev/name/{quote(company_name, safe='')}"
        f"?token={quote(token)}&format=png&size=96&fallback=monogram"
    )


def _fetch(company_name: str) -> tuple[bytes, str] | None:
    url = _provider_url(company_name)
    if not url:
        return None
    request = Request(url, headers={"User-Agent": "Cenvarn/1.0"})
    # _provider_url fixes the scheme and host; only the quoted path and provider token vary.
    with urlopen(request, timeout=5) as response:  # nosec B310
        mime_type = response.headers.get_content_type().lower()
        if mime_type not in _ALLOWED_MIME_TYPES:
            return None
        content = response.read(_MAX_IMAGE_BYTES + 1)
    if not content or len(content) > _MAX_IMAGE_BYTES:
        return None
    return content, mime_type


def get_or_fetch_logo(symbol: str, company_name: str) -> dict | None:
    symbol = (symbol or "?").strip().upper()
    company_name = (company_name or symbol).strip()
    key = provider_key(symbol, company_name)

    try:
        cached = db.get_company_logo(key)
    except Exception:
        cached = None
    if cached:
        return cached

    try:
        fetched = _fetch(company_name)
    except Exception:
        return None
    if not fetched:
        return None

    content, mime_type = fetched
    content_hash = hashlib.sha256(content).hexdigest()
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=_CACHE_DAYS)
    try:
        db.upsert_company_logo(
            key,
            symbol,
            company_name,
            mime_type,
            content,
            content_hash,
            expires_at,
        )
    except Exception:
        pass
    return {
        "provider_key": key,
        "symbol": symbol,
        "company_name": company_name,
        "mime_type": mime_type,
        "image_bytes": content,
        "content_hash": content_hash,
        "expires_at": expires_at,
    }
