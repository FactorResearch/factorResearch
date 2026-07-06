import requests

from ..data import cache

# =========================
# SEC company_tickers.json
# =========================

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    )
}

# Used only if the SEC endpoint is unavailable.
FALLBACK_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOG",
    "BRK.B",
    "JNJ",
    "V",
    "PG",
    "JPM",
    "UNH",
    "HD",
    "MA",
    "XOM",
]


def _fetch_sec_tickers() -> list[str]:
    """
    Load the complete SEC company ticker universe.

    No filtering is performed here. The universe intentionally includes
    every reporting company published by the SEC.

    Companies that are not suitable for Graham analysis (ETFs, funds,
    trusts, SPACs, shell companies, etc.) are removed later by the
    financial-data validation and screening pipeline rather than by
    unreliable name-based heuristics.
    """
    print("📋 Fetching SEC company universe...")

    try:
        response = requests.get(
            SEC_TICKERS_URL,
            headers=HEADERS,
            timeout=20,
        )
        response.raise_for_status()

        data = response.json()

        tickers = []

        for company in data.values():
            ticker = company.get("ticker", "").strip().upper()

            if not ticker:
                continue

            tickers.append(ticker)

        # Remove duplicates while preserving order
        tickers = list(dict.fromkeys(tickers))

        print(f"✅ Loaded {len(tickers):,} SEC tickers")

        return tickers

    except Exception as exc:
        print(f"⚠️ Failed to load SEC universe: {exc}")
        print("⚠️ Falling back to default ticker list.")
        return FALLBACK_TICKERS


def get_universe() -> list[str]:
    """
    Return the full SEC company universe.
    """
    cached = cache.read("universe", "sec_all")

    if cached:
        return cached

    universe = _fetch_sec_tickers()

    if universe:
        cache.write("universe", "sec_all", universe)

    return universe


def get_cached_universe() -> list[str]:
    """
    Return only companies whose SEC financial facts have already been cached.
    """
    return [
        ticker
        for ticker in get_universe()
        if cache.read("sec_facts", ticker) is not None
    ]


def get_graham_universe() -> list[str]:
    """
    Return the candidate universe for Graham analysis.

    The raw SEC universe is intentionally broad. Companies that fail
    Graham requirements are filtered later during data collection and
    score calculation.
    """
    return get_universe()