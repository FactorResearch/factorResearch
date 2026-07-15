"""FMP Pro adapter for Track E historical datasets."""

from __future__ import annotations

import os
from urllib.parse import urljoin

import requests

from codes.services import provider_gateway


class FMPError(RuntimeError):
    pass


class FMPClient:
    provider_name = "fmp"

    def __init__(self, api_key: str | None = None, base_url: str = "https://financialmodelingprep.com/stable/"):
        self.api_key = api_key or os.environ.get("FMP_API_KEY")
        if not self.api_key:
            raise FMPError("FMP_API_KEY is required for Track E ingestion.")
        self.base_url = base_url.rstrip("/") + "/"

    def _get(self, endpoint: str, **params) -> list[dict]:
        url = urljoin(self.base_url, endpoint.lstrip("/"))

        def fetch():
            response = requests.get(url, params=params, headers={"apikey": self.api_key}, timeout=20)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and payload.get("Error Message"):
                raise FMPError(payload["Error Message"])
            return payload if isinstance(payload, list) else [payload]

        result = provider_gateway.call("fmp", f"{endpoint}:{sorted(params.items())}", fetch, default=None, timeout=25)
        if result is None:
            raise FMPError(f"FMP request failed: {endpoint}")
        return result

    def profile(self, symbol: str) -> dict:
        rows = self._get("profile", symbol=symbol.upper())
        return rows[0] if rows else {}

    def search_cusip(self, cusip: str) -> list[dict]:
        return self._get("search-cusip", cusip=cusip)

    def search_isin(self, isin: str) -> list[dict]:
        return self._get("search-isin", isin=isin)

    def symbol_changes(self) -> list[dict]:
        return self._get("symbol-change")

    def delisted_companies(self, page: int = 0, limit: int = 100) -> list[dict]:
        return self._get("delisted-companies", page=page, limit=limit)

    def filings(self, symbol: str, start: str, end: str, limit: int = 100) -> list[dict]:
        return self._get("sec-filings-search/symbol", symbol=symbol.upper(), **{"from": start, "to": end}, page=0, limit=limit)

    def statements_as_reported(self, symbol: str) -> list[dict]:
        return self._get("financial-statement-full-as-reported", symbol=symbol.upper())

    def splits(self, symbol: str) -> list[dict]:
        return self._get("splits", symbol=symbol.upper())

    def dividends(self, symbol: str) -> list[dict]:
        return self._get("dividends", symbol=symbol.upper())

    def prices(self, symbol: str, start: str | None = None, end: str | None = None) -> list[dict]:
        params = {"symbol": symbol.upper()}
        if start:
            params["from"] = start
        if end:
            params["to"] = end
        return self._get("historical-price-eod/full", **params)

    def fx_history(self, pair: str, start: str | None = None, end: str | None = None) -> list[dict]:
        return self.prices(pair.upper(), start, end)

    def historical_constituents(self, index: str) -> list[dict]:
        endpoint = {"SP500": "historical-sp500-constituent", "NASDAQ": "historical-nasdaq-constituent", "DOWJONES": "historical-dowjones-constituent"}.get(index.upper())
        if not endpoint:
            raise ValueError(f"Unsupported FMP historical universe: {index}")
        return self._get(endpoint)
