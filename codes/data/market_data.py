"""Market-level data adapters."""

from __future__ import annotations

import pandas as pd

from codes.data import api_fetcher


def _first_price(symbols: tuple[str, ...]) -> float | None:
    for symbol in symbols:
        try:
            price = api_fetcher.get_price(symbol)
        except Exception as e:
            print(f"Market data price fetch failed for {symbol}: {e}")
            continue
        if price:
            return price
    return None


def _history(symbols: tuple[str, ...], years: int = 2) -> pd.DataFrame:
    for symbol in symbols:
        try:
            hist = api_fetcher.get_price_history(symbol, years=years)
        except Exception as e:
            print(f"Market data history fetch failed for {symbol}: {e}")
            continue
        if hist is not None and not hist.empty:
            return hist
    return pd.DataFrame()


def _spread_history(vix_hist: pd.DataFrame, vixeq_hist: pd.DataFrame) -> list[float]:
    if vix_hist is None or vixeq_hist is None or vix_hist.empty or vixeq_hist.empty:
        return []
    left = vix_hist[["Date", "Close"]].copy()
    right = vixeq_hist[["Date", "Close"]].copy()
    left["Date"] = pd.to_datetime(left["Date"], errors="coerce")
    right["Date"] = pd.to_datetime(right["Date"], errors="coerce")
    left["Close"] = pd.to_numeric(left["Close"], errors="coerce")
    right["Close"] = pd.to_numeric(right["Close"], errors="coerce")
    merged = left.merge(right, on="Date", suffixes=("_vix", "_vixeq"))
    merged = merged.dropna(subset=["Close_vix", "Close_vixeq"]).sort_values("Date")
    spreads = (merged["Close_vixeq"] - merged["Close_vix"]).tail(252)
    return [float(v) for v in spreads]


def get_market_fear_inputs() -> dict:
    """Fetch current VIX/VIXEQ readings and optional matched spread history."""
    vix_symbols = ("VIX", "^VIX")
    vixeq_symbols = ("VIXEQ", "^VIXEQ")

    vix = _first_price(vix_symbols)
    vixeq = _first_price(vixeq_symbols)
    spreads = []

    if vix is not None and vixeq is not None:
        vix_hist = _history(vix_symbols, years=2)
        vixeq_hist = _history(vixeq_symbols, years=2)
        spreads = _spread_history(vix_hist, vixeq_hist)

    return {"vix": vix, "vixeq": vixeq, "spread_history": spreads}
