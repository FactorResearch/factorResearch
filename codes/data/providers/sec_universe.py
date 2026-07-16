"""SEC ticker-universe infrastructure adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import requests

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")}


class SecTickerUniverseAdapter:
    """Map the SEC company-ticker payload to a stable symbol sequence."""

    def __init__(
        self,
        http_get: Callable[..., Any] = requests.get,
        *,
        url: str = SEC_TICKERS_URL,
        timeout_seconds: float = 20,
    ) -> None:
        self._http_get = http_get
        self._url = url
        self._timeout_seconds = timeout_seconds

    def read_tickers(self) -> list[str]:
        response = self._http_get(
            self._url,
            headers=SEC_HEADERS,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("SEC ticker response must be an object")

        symbols = []
        for company in payload.values():
            if not isinstance(company, Mapping):
                continue
            symbol = str(company.get("ticker", "")).strip().upper()
            if symbol:
                symbols.append(symbol)
        return list(dict.fromkeys(symbols))
