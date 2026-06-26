import pandas as pd
import requests
from io import StringIO
import json
from ..data import cache  # Assuming this is still needed for caching parts

# =========================
# SEC company_tickers.json source
# =========================
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Fallback tickers if needed
FALLBACK_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOG", "BRK.B",
                    "JNJ", "V", "PG", "JPM", "UNH", "HD", "MA", "XOM"]

def _fetch_sec_tickers() -> list[str]:
    """
    Fetch US equity tickers from SEC company_tickers.json.
    Filters to focus on securities (stocks), excluding ETFs where possible.
    """
    print("📋 Fetching US equity universe from SEC company_tickers.json...")
    try:
        resp = requests.get(SEC_TICKERS_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        
        tickers = []
        etf_keywords = ['ETF', 'ETN', 'Fund', 'Trust', 'Index', 'Series', 'Portfolio']
        
        for key, info in data.items():
            ticker = info.get('ticker', '').strip().upper()
            title = info.get('title', '').upper()
            
            if not ticker or ticker in ('', 'NAN', '-'):
                continue
            
            # Filter out likely ETFs and non-equity securities
            if any(kw in title for kw in etf_keywords):
                continue
            # Skip tickers that look like funds or have special suffixes common in ETFs
            if ticker.endswith(('.B', '-B', ' ETF', ' FUND')) or len(ticker) > 10:
                continue
            
            tickers.append(ticker)
        
        # Deduplicate while preserving order
        tickers = list(dict.fromkeys(tickers))
        
        print(f"✅ SEC Universe loaded: {len(tickers):,} unique securities (filtered ETFs)")
        return tickers
    except Exception as e:
        print(f" ⚠️ Failed to load SEC tickers: {e}")
        return FALLBACK_TICKERS

# Individual getters can reuse the same fetch since it's now one source
def get_universe() -> list[str]:
    cached = cache.read("universe", "sec_combined")
    if cached:
        return cached
    
    tickers = _fetch_sec_tickers()
    if tickers:
        cache.write("universe", "sec_combined", tickers)
    
    return tickers

def get_cached_universe() -> list[str]:
    """Only stocks with cached SEC data."""
    universe = get_universe()
    return [t for t in universe if cache.read("sec_facts", t) is not None]

def get_graham_universe() -> list[str]:
   
    all_tickers = get_universe()
    return all_tickers  # Fixed: return winners instead of cached

