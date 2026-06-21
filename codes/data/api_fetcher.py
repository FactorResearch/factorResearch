"""
Price data client — stooq via direct CSV download (no API key required).

Phase 0: all paid/keyed providers (Finnhub, Tiingo, Alpha Vantage) removed.
pandas_datareader was dropped (unmaintained, breaks on newer pandas —
deprecate_kwarg signature mismatch) in favour of hitting stooq's CSV
export endpoint directly via requests. EOD price data is sufficient for
fundamental analysis, so this module sources daily OHLCV history from
stooq and derives current price and monthly history from it. Cached via
codes.data.cache after first fetch.
"""

import time
import threading
from io import StringIO

import requests
import pandas as pd

from .cache import read, write

STOOQ_CSV_URL  = "https://stooq.com/q/d/l/"
STOOQ_HOME_URL = "https://stooq.com/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": STOOQ_HOME_URL,
}
_TIMEOUT = 15

# Stooq serves an anti-bot interstitial HTML page (not the CSV) to requests
# without a valid session cookie. A single persistent Session, warmed up by
# visiting the homepage once, gets the cookies needed for the CSV endpoint
# to behave — a one-shot GET to /q/d/l/ does not.
_session_lock = threading.Lock()
_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    with _session_lock:
        if _session is None:
            s = requests.Session()
            s.headers.update(_HEADERS)
            try:
                s.get(STOOQ_HOME_URL, timeout=_TIMEOUT)
            except Exception as e:
                print(f"  [Stooq] session warm-up failed: {e}")
            _session = s
        return _session


# ══════════════════════════════════════════════════════════════════════════════
# Backward-compat error type
# ══════════════════════════════════════════════════════════════════════════════

class RateLimitError(RuntimeError):
    """
    Kept for backward compatibility with callers (app.py, tests) that catch
    this type. Stooq has no enforced per-key rate limit, so this is not
    raised internally by this module anymore — only constructed directly
    by callers/tests that need the old error shape.
    """
    def __init__(self, provider: str, window: str, used: int, limit: int,
                resets_in: float | None = None):
        self.provider  = provider
        self.window    = window
        self.used      = used
        self.limit     = limit
        self.resets_in = resets_in

        reset_str = (
            f"  Resets in ~{int(resets_in)}s."
            if resets_in is not None
            else "  Resets at midnight (UTC)."
        )
        super().__init__(
            f"⚠️  [{provider}] Approaching {window} limit "
            f"({used}/{limit} calls used — processing paused to protect your quota)."
            f"{reset_str}"
        )


# ── Backward-compat: earnings_revision.py checks `_fh_client` via hasattr ─────
# Stooq has no SDK client; keep this attribute so callers that probe for a
# Finnhub client (and already degrade gracefully when it's None) don't crash.
_fh_client = None


# ══════════════════════════════════════════════════════════════════════════════
# Client-side throttle (polite to stooq; no key, no server-enforced limit)
# ══════════════════════════════════════════════════════════════════════════════

_throttle_lock = threading.Lock()
_last_call = 0.0
_MIN_GAP = 1.0  # seconds between stooq requests


def _throttle() -> None:
    global _last_call
    with _throttle_lock:
        gap = _MIN_GAP - (time.time() - _last_call)
        if gap > 0:
            time.sleep(gap)
        _last_call = time.time()


def _stooq_symbol(symbol: str) -> str:
    symbol = symbol.upper().strip()
    return symbol if "." in symbol else f"{symbol}.US"


# ══════════════════════════════════════════════════════════════════════════════
# Core fetch
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_stooq_daily(symbol: str, start: pd.Timestamp, _retry: bool = True) -> pd.DataFrame:
    """Daily Close history from stooq CSV export, oldest-first. Empty DataFrame on failure."""
    global _session
    sym = _stooq_symbol(symbol)
    _throttle()
    params = {
        "s": sym,
        "d1": start.strftime("%Y%m%d"),
        "d2": pd.Timestamp.now().strftime("%Y%m%d"),
        "i": "d",
    }
    session = _get_session()
    try:
        resp = session.get(STOOQ_CSV_URL, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        print(f"  [Stooq] error fetching {symbol}: {e}")
        return pd.DataFrame()

    # Failure modes: empty body, Polish "no data" message, anti-bot HTML page,
    # or a CSV with header row only (no price rows).
    stripped = text.strip()
    if (not stripped
            or "Brak danych" in stripped
            or "Exceeded" in stripped
            or stripped.startswith("<")):
        print(f"  [Stooq] no data / blocked response for {symbol} "
              f"(status={resp.status_code}, len={len(stripped)}, "
              f"preview={stripped[:80]!r})")
        if _retry:
            # Session may have gone stale (expired cookie) — drop it and
            # warm up a brand-new one, then try exactly once more.
            with _session_lock:
                _session = None
            return _fetch_stooq_daily(symbol, start, _retry=False)
        return pd.DataFrame()

    try:
        raw = pd.read_csv(StringIO(text))
    except Exception as e:
        print(f"  [Stooq] CSV parse error for {symbol}: {e} (preview={stripped[:80]!r})")
        return pd.DataFrame()

    if raw.empty or "Date" not in raw.columns or "Close" not in raw.columns:
        print(f"  [Stooq] unexpected CSV shape for {symbol}: columns={list(raw.columns)}")
        return pd.DataFrame()

    df = raw.sort_values("Date").reset_index(drop=True)
    df["Date"]  = pd.to_datetime(df["Date"])
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"])
    df = df[df["Close"] > 0]

    return df[["Date", "Close"]].reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# Public API — same signatures as before
# ══════════════════════════════════════════════════════════════════════════════

def get_price(symbol: str) -> float | None:
    """Most recent EOD close from stooq."""
    symbol = symbol.upper().strip()
    df = _fetch_stooq_daily(symbol, start=pd.Timestamp.now() - pd.Timedelta(days=21))
    if df.empty:
        return None
    price = float(df["Close"].iloc[-1])
    return round(price, 2) if price > 0 else None


def get_price_history(symbol: str, years: int = 10) -> pd.DataFrame:
    """
    Monthly EOD price history for `years` years.
    Returns DataFrame with columns: Date (str YYYY-MM-DD), Close (float).
    Cached after first fetch.
    """
    symbol = symbol.upper().strip()

    cached = read("hist", symbol)
    if cached:
        return pd.DataFrame(cached)

    cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
    daily  = _fetch_stooq_daily(symbol, start=cutoff)
    if daily.empty:
        return pd.DataFrame()

    try:
        monthly = (daily.set_index("Date").resample("ME").last()
                   .dropna(subset=["Close"]).reset_index())
    except ValueError:
        monthly = (daily.set_index("Date").resample("M").last()
                   .dropna(subset=["Close"]).reset_index())

    monthly["Date"]  = monthly["Date"].dt.strftime("%Y-%m-%d")
    monthly["Close"] = monthly["Close"].round(4)

    if not monthly.empty:
        write("hist", symbol, monthly.to_dict("records"))
    return monthly


def get_splits(symbol: str) -> list[dict]:
    """
    Stooq's free daily feed (via pandas_datareader) has no adjusted-close
    column, so split events can't be derived here. Returns [] — portfolio.py
    treats this as "no splits" (split factor = 1.0), which only affects
    share-count display/backtest precision for stocks that actually split
    during the holding period.
    """
    symbol = symbol.upper().strip()
    cached = read("splits", symbol)
    if cached is not None:
        return cached
    write("splits", symbol, [])
    return []


def get_insider_transactions(symbol: str, years: int = 1) -> list[dict]:
    """
    Insider transactions now come from SEC EDGAR Form 4 filings
    (codes.data.sec_data), not from this price client. Stub kept so
    existing callers don't break.
    """
    return []


def rate_limit_status() -> list[dict]:
    """No provider-enforced limits with stooq; kept for API compatibility."""
    return []


# ── Deprecated no-op shims (backward compat only) ──────────────────────────────

def _fh_rate_limit() -> None:
    pass


def _av_rate_limit() -> None:
    pass