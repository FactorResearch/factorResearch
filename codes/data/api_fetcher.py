"""
Price data client.

Source priority
───────────────
  Real-time quote : Finnhub (live) → Tiingo (EOD close fallback) → Alpha Vantage
  Price history   : Tiingo (primary) → Alpha Vantage (fallback)
  Split history   : Finnhub (explicit) → Tiingo (derived) → Alpha Vantage (derived)
  Option chains   : Finnhub (normalized, entitlement-dependent, 15-minute cache)

FMP has been removed — both /api/v3/ (legacy, dead Aug 2025) and /stable/
(paid only, 402 on free accounts) are no longer usable on free tier.

─────────────────────────────────────────────────────────────────────────────
Finnhub  — real-time quotes + explicit split history
  Free tier : 60 calls / minute
  Sign up   : https://finnhub.io/register
  Env var   : FINNHUB_API_KEY=your_key
  Install   : pip install finnhub-python

Tiingo  — primary EOD history (20yr+), derived splits, EOD quote fallback
  Free tier : 500 calls / day, 50 calls / hour  (no credit card required)
  Sign up   : https://tiingo.com
  Env var   : TIINGO_API_KEY=your_key
  Auth      : Authorization: Token <key>  header  (no SDK needed)
  Endpoint  : https://api.tiingo.com/tiingo/daily/{ticker}/prices
              ?startDate=YYYY-MM-DD&token=KEY
  Returns   : close (unadjusted) + adjClose (split+dividend adjusted)
  Splits    : derived by detecting adjClose/close ratio jumps across days
              — no dedicated splits endpoint exists on Tiingo

Alpha Vantage  — last-resort fallback for history and splits
  Free tier : 25 calls / day, 5 calls / minute
  Sign up   : https://www.alphavantage.co/support/#api-key
  Env var   : AV_API_KEY=your_key

─────────────────────────────────────────────────────────────────────────────
RATE LIMITING
  Each provider is tracked by a RateLimiter (sliding-window call log).
  Two thresholds apply per window:

    WARN_PCT  (80 %) — warning printed, request still proceeds
    BLOCK_PCT (95 %) — RateLimitError raised, no request made

  Callers should catch RateLimitError:

    from price_client import RateLimitError, get_price

    try:
        price = get_price("NVDA")
    except RateLimitError as e:
        print(e)   # ⚠️  [Tiingo] Approaching daily limit (475/500 calls used …)

  Limits tracked:
    Finnhub       — 60 / minute
    Tiingo        — 50 / hour  AND  500 / day
    Alpha Vantage — 5 / minute  AND  25 / day

─────────────────────────────────────────────────────────────────────────────
BACKWARDS-COMPATIBLE SHIMS
  _fh_rate_limit() and _av_rate_limit() are kept as no-op shims so any
  module that imports them (e.g. EarningsRevision via alpha_vantage_client)
  does not break with AttributeError.  Migrate those callers to use the
  RateLimiter instances directly when convenient.
"""

import fcntl
import os
import time
import collections
import requests
import finnhub
import pandas as pd
from pathlib import Path

from .cache import read, read_entry, write
from .options_chain import (
    FinnhubOptionsChainProvider,
    OptionsChainProvider,
    OptionsChainProviderError,
    unavailable_chain,
)
from codes.core.config import cache_root


# ══════════════════════════════════════════════════════════════════════════════
# Rate-limit infrastructure
# ══════════════════════════════════════════════════════════════════════════════

class RateLimitError(RuntimeError):
    """
    Raised before a request is made when a provider is at or near its ceiling.

    Attributes
    ----------
    provider  : str          e.g. "Tiingo", "Finnhub", "AlphaVantage"
    window    : str          "per-minute", "hourly", or "daily"
    used      : int          calls made in the current window
    limit     : int          hard ceiling for this window
    resets_in : float | None seconds until the window resets (None = daily)
    """
    def __init__(
        self,
        provider: str,
        window: str,
        used: int,
        limit: int,
        resets_in: float | None = None,
    ):
        self.provider  = provider
        self.window    = window
        self.used      = used
        self.limit     = limit
        self.resets_in = resets_in

        reset_str = (
            f" Please retry in approximately {int(resets_in)}s."
            if resets_in is not None
            else " Please retry after the market close or try again later."
        )
        self.user_message = (
            f"Service temporarily unavailable due to API rate limiting.{reset_str}"
        )
        self.raw_message = (
            f"⚠️  [{provider}] Approaching {window} limit "
            f"({used}/{limit} calls used — processing paused to protect your quota)."
            f"{reset_str}"
        )
        super().__init__(self.raw_message)

    def __str__(self) -> str:
        return self.raw_message

    def debug_message(self) -> str:
        return self.raw_message


class _Window:
    """
    Sliding-window call counter.

    span_seconds : width of the rolling window  (60, 3600, or 86400)
    limit        : hard call ceiling within the window
    warn_pct     : fraction at which a warning is emitted      (default 0.80)
    block_pct    : fraction at which RateLimitError is raised  (default 0.95)
    """

    def __init__(
        self,
        span_seconds: int,
        limit: int,
        warn_pct: float = 0.80,
        block_pct: float = 0.95,
    ):
        self.span     = span_seconds
        self.limit    = limit
        self.warn_at  = int(limit * warn_pct)
        self.block_at = int(limit * block_pct)
        self._calls: collections.deque[float] = collections.deque()

    def _evict(self) -> None:
        cutoff = time.time() - self.span
        while self._calls and self._calls[0] < cutoff:
            self._calls.popleft()

    @property
    def used(self) -> int:
        self._evict()
        return len(self._calls)

    @property
    def resets_in(self) -> float:
        self._evict()
        if not self._calls:
            return 0.0
        return max(0.0, self._calls[0] + self.span - time.time())

    def check(self, provider: str, window_label: str) -> None:
        n = self.used
        if n >= self.block_at:
            raise RateLimitError(
                provider=provider,
                window=window_label,
                used=n,
                limit=self.limit,
                resets_in=self.resets_in if self.span < 86400 else None,
            )
        if n >= self.warn_at:
            ri    = int(self.resets_in)
            label = f"~{ri}s" if self.span < 86400 else "midnight UTC"
            print(
                f"  ⚠️  [{provider}] {window_label} limit warning: "
                f"{n}/{self.limit} calls used.  Resets in {label}."
            )

    def record(self) -> None:
        self._calls.append(time.time())

    def force_fill(self) -> None:
        """Mark window as full (used when the API itself returns a rate-limit error)."""
        now = time.time()
        while len(self._calls) < self.limit:
            self._calls.append(now)


class RateLimiter:
    """
    Composite rate limiter supporting multiple independent windows per provider.

    Usage
    -----
        limiter.check()    # raises RateLimitError if any window near ceiling
        # … make the API call …
        limiter.record()   # log timestamp in all windows

    windows : list of (span_seconds, limit, label)
        e.g. [(3600, 50, "hourly"), (86400, 500, "daily")]
    """

    def __init__(self, provider: str, windows: list[tuple[int, int, str]]):
        self.provider = provider
        self._windows = [
            (_Window(span, lim), label)
            for span, lim, label in windows
        ]

    def check(self) -> None:
        for win, label in self._windows:
            win.check(self.provider, label)

    def record(self) -> None:
        for win, _ in self._windows:
            win.record()

    def force_fill(self) -> None:
        for win, _ in self._windows:
            win.force_fill()

    def status(self) -> list[dict]:
        return [
            {
                "provider":  self.provider,
                "window":    label,
                "used":      win.used,
                "limit":     win.limit,
                "resets_in": round(win.resets_in, 1),
            }
            for win, label in self._windows
        ]


# ── Per-provider limiters ─────────────────────────────────────────────────────
_fh_limiter = RateLimiter(
    provider="Finnhub",
    windows=[(60, 60, "per-minute")],
)

_tiingo_limiter = RateLimiter(
    provider="Tiingo",
    windows=[
        (3600,  50,  "hourly"),
        (86400, 500, "daily"),
    ],
)

_av_limiter = RateLimiter(
    provider="AlphaVantage",
    windows=[
        (60,    5,  "per-minute"),
        (86400, 25, "daily"),
    ],
)

_price_history_lock_path = cache_root()

class _FileLock:
    def __init__(self, path: Path):
        self.path = path
        self._fp = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self.path.open("a")
        fcntl.flock(self._fp, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._fp:
                fcntl.flock(self._fp, fcntl.LOCK_UN)
                self._fp.close()
        finally:
            self._fp = None


def _is_price_history_cache_fresh(entry: dict) -> bool:
    ts = entry.get("ts")
    if not isinstance(ts, (int, float)):
        return False
    return time.time() - ts < 24 * 60 * 60


# ══════════════════════════════════════════════════════════════════════════════
# Provider config
# ══════════════════════════════════════════════════════════════════════════════

# Finnhub
def _is_usable_api_key(value: str | None) -> bool:
    """Reject unset and example credentials before making provider requests."""
    normalized = (value or "").strip().lower()
    return normalized not in {
        "",
        "your_api_key_here",
        "your_api_key",
        "replace_me",
        "changeme",
    }


FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
FINNHUB_CONFIGURED = _is_usable_api_key(FINNHUB_API_KEY)
_fh_client: finnhub.Client | None = (
    finnhub.Client(api_key=FINNHUB_API_KEY) if FINNHUB_CONFIGURED else None
)

try:
    OPTIONS_CHAIN_CACHE_TTL = max(60, int(os.getenv("OPTIONS_CHAIN_CACHE_TTL", "900")))
except ValueError:
    OPTIONS_CHAIN_CACHE_TTL = 900


def is_finnhub_configured() -> bool:
    """Whether a non-placeholder Finnhub credential is available to this process."""
    return FINNHUB_CONFIGURED

# Tiingo
TIINGO_API_KEY  = os.getenv("TIINGO_API_KEY", "")
TIINGO_BASE_URL = "https://api.tiingo.com/tiingo/daily"
_TIINGO_HEADERS = {
    "Content-Type":  "application/json",
    "Authorization": f"Token {TIINGO_API_KEY}",
}

# Alpha Vantage
AV_API_KEY  = os.getenv("AV_API_KEY", "demo")
AV_BASE_URL = "https://www.alphavantage.co/query"

_TIMEOUT    = 30
_MAX_RETRY  = 3
_RETRY_WAIT = 5


# ══════════════════════════════════════════════════════════════════════════════
# HTTP helper
# ══════════════════════════════════════════════════════════════════════════════

def _get(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
) -> dict | list | None:
    """GET with retry.  Rate-limit check/record handled by each caller."""
    for attempt in range(1, _MAX_RETRY + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 429:
                print(f"  429 rate-limit from server (attempt {attempt}/{_MAX_RETRY})")
                # Don't retry 429 — surface it so the limiter can handle it
                return None
            print(f"  HTTP {status} error (attempt {attempt}/{_MAX_RETRY}): {e}")
            if attempt < _MAX_RETRY:
                time.sleep(_RETRY_WAIT)
        except requests.exceptions.Timeout:
            print(f"  Timeout (attempt {attempt}/{_MAX_RETRY}), retrying in {_RETRY_WAIT}s...")
            if attempt < _MAX_RETRY:
                time.sleep(_RETRY_WAIT)
        except requests.exceptions.ConnectionError as e:
            print(f"  Connection error (attempt {attempt}/{_MAX_RETRY}): {e}")
            if attempt < _MAX_RETRY:
                time.sleep(_RETRY_WAIT)
        except Exception as e:
            print(f"  Unexpected error (attempt {attempt}/{_MAX_RETRY}): {e}")
            if attempt < _MAX_RETRY:
                time.sleep(_RETRY_WAIT)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Finnhub  — real-time quotes + explicit split history
# ══════════════════════════════════════════════════════════════════════════════

def _fh_get_price(symbol: str) -> float | None:
    """Live quote from Finnhub SDK.  Raises RateLimitError if near per-minute ceiling."""
    if not _fh_client:
        return None
    _fh_limiter.check()
    try:
        quote = _fh_client.quote(symbol.upper())
        _fh_limiter.record()
        price = quote.get("c")
        if price and float(price) > 0:
            return round(float(price), 2)
    except RateLimitError:
        raise
    except Exception as e:
        print(f"  [Finnhub] quote error for {symbol}: {e}")
    return None


def _fh_get_splits(symbol: str) -> list[dict]:
    """
    Explicit split history from Finnhub.
    Returns [{"date": "YYYY-MM-DD", "ratio": float}, ...] oldest-first.
      ratio > 1.0 → forward split  (e.g. 4.0 = 4-for-1)
      ratio < 1.0 → reverse split  (e.g. 0.1 = 1-for-10)

    NOTE: earnings_surprises(), eps_estimates(), revenue_estimates() do NOT
    exist on the Finnhub free-tier SDK.  Callers must catch AttributeError.
    """
    if not _fh_client:
        return []
    _fh_limiter.check()
    try:
        today  = time.strftime("%Y-%m-%d")
        result = _fh_client.stock_splits(symbol.upper(), _from="2000-01-01", to=today)
        _fh_limiter.record()
        splits = []
        for item in result.get("data") or []:
            from_f = float(item.get("fromFactor", 1) or 1)
            to_f   = float(item.get("toFactor",   1) or 1)
            if from_f > 0 and to_f > 0 and abs(to_f / from_f - 1.0) > 0.001:
                splits.append({
                    "date":  item["date"],
                    "ratio": round(to_f / from_f, 6),
                })
        return sorted(splits, key=lambda x: x["date"])
    except RateLimitError:
        raise
    except Exception as e:
        print(f"  [Finnhub] splits error for {symbol}: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Tiingo  — EOD history (primary), EOD quote (fallback), derived splits
# ══════════════════════════════════════════════════════════════════════════════

def _tiingo_get(url: str, params: dict | None = None) -> dict | list | None:
    """
    Tiingo GET with rate-limit guard.
    Auth is passed via the Authorization header (set at module load).
    Raises RateLimitError if hourly or daily ceiling is near.
    Forces window fill if the server returns 429.
    """
    if not TIINGO_API_KEY:
        return None
    _tiingo_limiter.check()
    result = _get(url, params=params, headers=_TIINGO_HEADERS)
    if result is None:
        # _get returns None on 429 — fill limiter so next check() blocks
        _tiingo_limiter.force_fill()
        raise RateLimitError(
            provider="Tiingo",
            window="hourly (API-enforced)",
            used=_tiingo_limiter._windows[0][0].used,
            limit=_tiingo_limiter._windows[0][0].limit,
            resets_in=_tiingo_limiter._windows[0][0].resets_in,
        )
    _tiingo_limiter.record()
    return result


def _tiingo_get_price(symbol: str) -> float | None:
    """
    Latest EOD close from Tiingo.
    Endpoint: GET /tiingo/daily/{ticker}/prices  (returns last available close)
    NOT a live intraday quote — use Finnhub for that.
    """
    try:
        print(f"  [Tiingo] fetching latest EOD price for {symbol}...")
        url  = f"{TIINGO_BASE_URL}/{symbol.lower()}/prices"
        data = _tiingo_get(url)
        if data and isinstance(data, list) and len(data) > 0:
            price = data[-1].get("close") or data[-1].get("adjClose")
            if price and float(price) > 0:
                return round(float(price), 2)
    except RateLimitError:
        raise
    except Exception as e:
        print(f"  [Tiingo] price error for {symbol}: {e}")
    return None


def _tiingo_get_price_history(symbol: str, years: int = 10) -> pd.DataFrame:
    """
    Daily EOD history from Tiingo, resampled to monthly.

    Endpoint : GET /tiingo/daily/{ticker}/prices
               ?startDate=YYYY-MM-DD  (client-side date param, supported)
    Response : [{"date": ..., "close": float, "adjClose": float, ...}, ...]

    Both raw close and adjClose are stored — we use close (unadjusted) to
    match the existing stack's convention.  adjClose is retained in the
    DataFrame for callers that need split-adjusted values.

    Splits: derived here by detecting adjClose/close ratio jumps > 0.5%
    between consecutive days.  Stored separately via _tiingo_derive_splits().
    """
    try:
        cutoff     = pd.Timestamp.now() - pd.DateOffset(years=years)
        start_date = cutoff.strftime("%Y-%m-%d")

        print(f"  [Tiingo] fetching {years}yr history for {symbol}...")
        url  = f"{TIINGO_BASE_URL}/{symbol.lower()}/prices"
        data = _tiingo_get(url, params={"startDate": start_date})

        if not data or not isinstance(data, list):
            print(f"  [Tiingo] no history returned for {symbol}")
            return pd.DataFrame()

    except RateLimitError:
        raise
    except Exception as e:
        print(f"  [Tiingo] history error for {symbol}: {e}")
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df.columns = [c.strip().lower() for c in df.columns]

    if "date" not in df.columns or "close" not in df.columns:
        print(f"  [Tiingo] unexpected response shape for {symbol}: {list(df.columns)}")
        return pd.DataFrame()

    df["Date"]     = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.tz_localize(None)
    df["Close"]    = pd.to_numeric(df["close"],    errors="coerce")
    df["AdjClose"] = pd.to_numeric(df.get("adjclose", df["close"]), errors="coerce")
    df = df[["Date", "Close", "AdjClose"]].dropna(subset=["Date", "Close"])
    df = df.sort_values("Date").reset_index(drop=True)

    # Client-side filter (belt-and-suspenders — startDate param usually handles it)
    df = df[df["Date"] >= cutoff].reset_index(drop=True)
    print(f"  [Tiingo] {len(df)} daily rows for {symbol}, filtering client-side to {years}yr")

    if df.empty:
        return pd.DataFrame()

    # Resample to monthly (last trading day of each month)
    try:
        df = df.set_index("Date").resample("ME").last().dropna(subset=["Close"]).reset_index()
    except ValueError:
        df = df.set_index("Date").resample("M").last().dropna(subset=["Close"]).reset_index()

    df["Date"]     = df["Date"].dt.strftime("%Y-%m-%d")
    df["Close"]    = df["Close"].round(4)
    df["AdjClose"] = df["AdjClose"].round(4)
    print(f"  [Tiingo] {len(df)} monthly rows for {symbol} ({years}yr)")
    return df


def _tiingo_derive_splits(symbol: str, years: int = 10) -> list[dict]:
    """
    Derive split events from Tiingo daily price history by detecting
    step-changes in the adjClose / close ratio.

    A ratio jump > 0.5% between consecutive trading days indicates a
    corporate action (split or large special dividend) on that date.

    This is an approximation — it cannot distinguish splits from special
    dividends, and the ratio may differ slightly from the true split factor.
    Use Finnhub's explicit split endpoint when exact ratios are needed.

    Returns [{"date": "YYYY-MM-DD", "ratio": float}, ...] oldest-first.
    """
    try:
        cutoff     = pd.Timestamp.now() - pd.DateOffset(years=years)
        start_date = cutoff.strftime("%Y-%m-%d")
        url        = f"{TIINGO_BASE_URL}/{symbol.lower()}/prices"
        data       = _tiingo_get(url, params={"startDate": start_date})

        if not data or not isinstance(data, list):
            return []
    except RateLimitError:
        raise
    except Exception as e:
        print(f"  [Tiingo] derive_splits error for {symbol}: {e}")
        return []

    df = pd.DataFrame(data)
    df.columns = [c.strip().lower() for c in df.columns]

    if "date" not in df.columns or "close" not in df.columns or "adjclose" not in df.columns:
        return []

    df["date"]     = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.tz_localize(None)
    df["close"]    = pd.to_numeric(df["close"],    errors="coerce")
    df["adjclose"] = pd.to_numeric(df["adjclose"], errors="coerce")
    df = df.dropna(subset=["date", "close", "adjclose"])
    df = df[df["close"] > 0].sort_values("date").reset_index(drop=True)

    df["ratio"] = df["adjclose"] / df["close"]
    df["ratio_prev"] = df["ratio"].shift(1)
    df["ratio_chg"]  = (df["ratio"] - df["ratio_prev"]).abs() / df["ratio_prev"].abs()

    # Flag days where the ratio changed by more than 0.5%
    splits_df = df[df["ratio_chg"] > 0.005].copy()

    splits = []
    for _, row in splits_df.iterrows():
        if pd.notna(row["ratio_prev"]) and row["ratio_prev"] > 0:
            factor = round(row["ratio"] / row["ratio_prev"], 6)
            splits.append({
                "date":  row["date"].strftime("%Y-%m-%d"),
                "ratio": factor,
            })

    return sorted(splits, key=lambda x: x["date"])


# ══════════════════════════════════════════════════════════════════════════════
# Alpha Vantage  — last-resort fallback
# ══════════════════════════════════════════════════════════════════════════════

def _av_get(params: dict) -> dict | None:
    """
    Alpha Vantage GET with rate-limit guard.
    Raises RateLimitError on pre-flight check or on API-returned rate-limit body.
    """
    _av_limiter.check()

    data = _get(AV_BASE_URL, params=params)
    if not data:
        return None

    if "Error Message" in data:
        print(f"  [AlphaVantage] API error: {data['Error Message']}")
        return None

    if "Note" in data or "Information" in data:
        msg = data.get("Note") or data.get("Information", "")
        print(f"  [AlphaVantage] API rate-limit response: {msg[:120]}")
        _av_limiter.force_fill()
        raise RateLimitError(
            provider="AlphaVantage",
            window="per-minute (API-enforced)",
            used=_av_limiter._windows[0][0].used,
            limit=_av_limiter._windows[0][0].limit,
            resets_in=60.0,
        )

    _av_limiter.record()
    return data


def _av_get_price(symbol: str) -> float | None:
    data = _av_get({
        "function": "GLOBAL_QUOTE",
        "symbol":   symbol.upper(),
        "apikey":   AV_API_KEY,
    })
    if not data:
        return None
    price_str = data.get("Global Quote", {}).get("05. price")
    if price_str:
        try:
            p = float(price_str)
            return round(p, 2) if p > 0 else None
        except (ValueError, TypeError):
            pass
    return None


def _av_get_price_history(symbol: str, years: int = 10) -> pd.DataFrame:
    data = _av_get({
        "function": "TIME_SERIES_MONTHLY",
        "symbol":   symbol.upper(),
        "apikey":   AV_API_KEY,
    })
    if not data:
        return pd.DataFrame()

    ts = data.get("Monthly Time Series", {})
    if not ts:
        return pd.DataFrame()

    cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
    rows   = []
    for date_str, vals in ts.items():
        dt = pd.to_datetime(date_str)
        if dt >= cutoff:
            rows.append({
                "Date":     dt.strftime("%Y-%m-%d"),
                "Close":    float(vals["4. close"]),
                "AdjClose": float(vals["4. close"]),  # AV monthly has no adjClose
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    return df


def _av_get_splits(symbol: str) -> list[dict]:
    data = _av_get({
        "function": "TIME_SERIES_MONTHLY_ADJUSTED",
        "symbol":   symbol.upper(),
        "apikey":   AV_API_KEY,
    })
    if not data:
        return []

    ts     = data.get("Monthly Adjusted Time Series", {})
    splits = []
    for date_str, vals in ts.items():
        try:
            coeff = float(vals.get("8. split coefficient", 1) or 1)
            if abs(coeff - 1.0) > 0.001:
                splits.append({"date": date_str, "ratio": round(coeff, 6)})
        except (ValueError, TypeError):
            continue
    return sorted(splits, key=lambda x: x["date"])


# ══════════════════════════════════════════════════════════════════════════════
# Public API — drop-in replacement, same signatures throughout
# ══════════════════════════════════════════════════════════════════════════════

def get_price(symbol: str) -> float | None:
    """
    Current price.
    Priority: Finnhub (live) → Tiingo (EOD close) → Alpha Vantage (EOD close)

    Finnhub gives a live intraday price during market hours.
    Tiingo and Alpha Vantage give the most recent EOD close.

    Raises RateLimitError if the active provider is near its ceiling.
    RateLimitError from Finnhub is NOT silently swallowed — it propagates
    immediately so the caller can surface it rather than burning Tiingo quota.
    """
    symbol = symbol.upper().strip()

    if _fh_client:
        print(f"  [Finnhub] fetching price for {symbol}...")
        try:
            price = _fh_get_price(symbol)
            if price:
                return price
            print(f"  [Finnhub] no price returned, trying Tiingo...")
        except RateLimitError:
            raise

    if TIINGO_API_KEY:
        try:
            price = _tiingo_get_price(symbol)
            if price:
                return price
            print(f"  [Tiingo] no price returned, trying Alpha Vantage...")
        except RateLimitError:
            raise

    print(f"  [AlphaVantage] fetching price for {symbol}...")
    return _av_get_price(symbol)


def get_price_history(symbol: str, years: int = 10) -> pd.DataFrame:
    """
    Monthly EOD price history for `years` years.
    Priority: Tiingo (primary) → Alpha Vantage (fallback)

    Returns a DataFrame with columns: Date (str YYYY-MM-DD), Close (float),
    AdjClose (float).  Cached after first fetch.

    Raises RateLimitError if the active provider is near its ceiling.
    """
    symbol = symbol.upper().strip()
    lock_path = _price_history_lock_path / f"hist-{symbol.lower()}.lock"

    with _FileLock(lock_path):
        entry = read_entry("hist", symbol)
        if entry is not None and _is_price_history_cache_fresh(entry):
            return pd.DataFrame(entry["data"])

        df = pd.DataFrame()

        if TIINGO_API_KEY:
            try:
                df = _tiingo_get_price_history(symbol, years)
            except RateLimitError:
                raise
            if df.empty:
                print(f"  [Tiingo] no history returned, falling back to Alpha Vantage...")

        if df.empty:
            print(f"  [AlphaVantage] fetching {years}yr history for {symbol}...")
            df = _av_get_price_history(symbol, years)

        if not df.empty:
            write("hist", symbol, df.to_dict("records"))

        return df


def get_splits(symbol: str) -> list[dict]:
    """
    Full split history, sorted oldest-first.
    Each item: {"date": "YYYY-MM-DD", "ratio": float}
      ratio > 1.0 → forward split  (share count × ratio)
      ratio < 1.0 → reverse split  (share count ÷ 1/ratio)

    Priority:
      1. Finnhub  — explicit split dates and exact ratios          (best)
      2. Tiingo   — derived from adjClose/close ratio jumps        (approximate)
      3. Alpha Vantage — derived from split coefficient field      (approximate)

    Cached after first fetch.
    Raises RateLimitError if the active provider is near its ceiling.
    """
    symbol = symbol.upper().strip()

    cached = read("splits", symbol)
    if cached is not None:
        return cached

    splits = []

    if _fh_client:
        print(f"  [Finnhub] fetching split history for {symbol}...")
        try:
            splits = _fh_get_splits(symbol)
        except RateLimitError:
            raise

    if not splits and TIINGO_API_KEY:
        print(f"  [Tiingo] deriving split history for {symbol}...")
        try:
            splits = _tiingo_derive_splits(symbol)
        except RateLimitError:
            raise

    if not splits:
        print(f"  [AlphaVantage] fetching split history for {symbol}...")
        splits = _av_get_splits(symbol)

    write("splits", symbol, splits)
    return splits


# ══════════════════════════════════════════════════════════════════════════════
# Option chains — provider-neutral normalized snapshots
# ══════════════════════════════════════════════════════════════════════════════

def _options_chain_cache_key(provider_name: str, symbol: str) -> str:
    safe_provider = "".join(
        char for char in provider_name.strip().lower() if char.isalnum() or char in "_-"
    ) or "unknown"
    return f"{safe_provider}-{symbol.lower()}"


def _options_chain_cache_is_fresh(entry: dict | None) -> bool:
    if not isinstance(entry, dict) or not isinstance(entry.get("ts"), (int, float)):
        return False
    return time.time() - entry["ts"] < OPTIONS_CHAIN_CACHE_TTL


def _stale_options_chain(entry: dict, *, error: str | None = None) -> dict | None:
    payload = entry.get("data")
    if not isinstance(payload, dict) or not isinstance(payload.get("contracts"), list):
        return None
    stale = dict(payload)
    stale["status"] = "STALE"
    stale["error"] = error
    stale["contract_count"] = len(stale["contracts"])
    return stale


def _get_options_chain_unlocked(
    symbol: str,
    *,
    provider: OptionsChainProvider | None = None,
    force_refresh: bool = False,
) -> dict:
    """Return a normalized, short-lived option-chain snapshot.

    Finnhub is the default live adapter.  A provider can be injected for tests
    or future vendors as long as it implements ``OptionsChainProvider``.
    Provider failures never masquerade as live data: a prior snapshot is marked
    ``STALE`` and otherwise a stable empty status is returned.
    """
    symbol = symbol.upper().strip()
    if not symbol:
        raise ValueError("symbol is required")

    provider_name = str(getattr(provider, "name", "FINNHUB")).upper().strip() or "UNKNOWN"
    cache_key = _options_chain_cache_key(provider_name, symbol)
    cache_entry = read_entry("options_chain", cache_key)
    if not force_refresh and _options_chain_cache_is_fresh(cache_entry):
        cached = cache_entry.get("data")
        if isinstance(cached, dict):
            return cached

    active_provider = provider
    if active_provider is None:
        if _fh_client is None:
            stale = _stale_options_chain(
                cache_entry,
                error="Live option-chain provider is not configured.",
            ) if cache_entry else None
            if stale is not None:
                return stale
            return unavailable_chain(
                symbol,
                provider="FINNHUB",
                status="CONFIGURATION_REQUIRED",
                error="FINNHUB_API_KEY is not configured.",
            )
        active_provider = FinnhubOptionsChainProvider(
            _fh_client,
            before_request=_fh_limiter.check,
            after_request=_fh_limiter.record,
        )

    try:
        snapshot = active_provider.fetch_chain(symbol)
        payload = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
        if not isinstance(payload, dict) or not isinstance(payload.get("contracts"), list):
            raise OptionsChainProviderError("Provider returned an invalid normalized chain")
        payload["contract_count"] = len(payload["contracts"])
        write("options_chain", cache_key, payload)
        return payload
    except RateLimitError:
        stale = _stale_options_chain(
            cache_entry,
            error="Provider rate limit reached; using the last chain snapshot.",
        ) if cache_entry else None
        if stale is not None:
            return stale
        raise
    except Exception as exc:
        print(f"  [{provider_name}] option_chain error for {symbol}: {type(exc).__name__}: {exc}")
        stale = _stale_options_chain(
            cache_entry,
            error="Live refresh failed; using the last chain snapshot.",
        ) if cache_entry else None
        if stale is not None:
            return stale
        return unavailable_chain(
            symbol,
            provider=provider_name,
            status="PROVIDER_ERROR",
            error=f"Option-chain refresh failed ({type(exc).__name__}).",
        )


def get_options_chain(
    symbol: str,
    *,
    provider: OptionsChainProvider | None = None,
    force_refresh: bool = False,
) -> dict:
    """Thread/process-safe wrapper around the normalized chain refresh."""
    normalized_symbol = symbol.upper().strip()
    if not normalized_symbol:
        raise ValueError("symbol is required")
    provider_name = str(getattr(provider, "name", "FINNHUB")).upper().strip() or "UNKNOWN"
    cache_key = _options_chain_cache_key(provider_name, normalized_symbol)
    lock_path = Path(".cache") / f"options-chain-{cache_key}.lock"
    with _FileLock(lock_path):
        return _get_options_chain_unlocked(
            normalized_symbol,
            provider=provider,
            force_refresh=force_refresh,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Insider transactions  — Finnhub only (no free-tier fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _fh_get_insider_transactions(symbol: str, years: int = 1) -> list[dict]:
    """Open-market insider transactions from Finnhub (codes P and S only)."""
    if not _fh_client:
        return []
    _fh_limiter.check()
    try:
        cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
        result = _fh_client.stock_insider_transactions(
            symbol.upper(),
            _from=cutoff.strftime("%Y-%m-%d"),
            to=pd.Timestamp.now().strftime("%Y-%m-%d"),
        )
        _fh_limiter.record()
        out = []
        for item in (result.get("data") or []):
            code   = str(item.get("transactionCode", "")).strip().upper()
            change = float(item.get("change") or 0)
            if code == "P":
                tx, is_open = "buy",  True
            elif code == "S":
                tx, is_open = "sell", True
            elif change > 0:
                tx, is_open = "buy",  False
            elif change < 0:
                tx, is_open = "sell", False
            else:
                continue
            shares = abs(change)
            if shares <= 0:
                continue
            out.append({
                "date":           item.get("transactionDate") or item.get("filingDate", ""),
                "insider_id":     str(item.get("name", "unknown")),
                "role":           str(item.get("relationship", "")),
                "transaction":    tx,
                "shares":         shares,
                "is_open_market": is_open,
            })
        return out
    except RateLimitError:
        raise
    except Exception as e:
        print(f"  [Finnhub] insider_transactions error for {symbol}: {e}")
        return []


def get_insider_transactions(symbol: str, years: int = 1) -> list[dict]:
    """
    Insider transaction history (cached).
    Returns list compatible with insider_activity.get_insider_score().
    Empty list when Finnhub key is absent.
    """
    symbol = symbol.upper().strip()
    cached = read("insiders", symbol)
    if cached is not None:
        return cached
    transactions = _fh_get_insider_transactions(symbol, years) if _fh_client else []
    write("insiders", symbol, transactions)
    return transactions


# ══════════════════════════════════════════════════════════════════════════════
# Phase E alternative-data provider feeds — Finnhub
# ══════════════════════════════════════════════════════════════════════════════

def _period_from_date(value: object, granularity: str = "quarter") -> str:
    try:
        ts = pd.Timestamp(str(value)[:10])
    except Exception:
        ts = pd.Timestamp.now()
    if granularity == "year":
        return str(ts.year)
    quarter = ((ts.month - 1) // 3) + 1
    return f"{ts.year}-Q{quarter}"


def _as_records_by_period(
    rows: list[dict],
    *,
    date_keys: tuple[str, ...],
    value_keys: tuple[str, ...],
    granularity: str = "quarter",
) -> list[dict]:
    by_period: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_value = next((row.get(k) for k in date_keys if row.get(k)), None)
        period = _period_from_date(date_value, granularity=granularity)
        value = None
        for key in value_keys:
            try:
                raw = row.get(key)
                if raw is not None:
                    value = float(raw)
                    break
            except (TypeError, ValueError):
                continue
        if value is None:
            value = 1.0
        by_period[period] = by_period.get(period, 0.0) + value
    return [
        {"period": period, "value": round(value, 4)}
        for period, value in sorted(by_period.items())
    ]


def _payload_rows(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("ownership") or payload.get("patent") or []
    else:
        rows = payload or []
    return rows if isinstance(rows, list) else []


def _fh_get_institutional_ownership_trends(symbol: str, years: int = 2) -> list[dict]:
    """Institutional ownership trend records from Finnhub, aggregated by quarter."""
    if not _fh_client:
        return []
    _fh_limiter.check()
    try:
        end = pd.Timestamp.now()
        start = end - pd.DateOffset(years=years)
        payload = _fh_client.institutional_ownership(
            symbol.upper(),
            None,
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )
        _fh_limiter.record()
        return _as_records_by_period(
            _payload_rows(payload),
            date_keys=("reportDate", "filingDate", "date", "period"),
            value_keys=("share", "shares", "ownership", "value", "marketValue"),
            granularity="quarter",
        )
    except RateLimitError:
        raise
    except Exception as e:
        print(f"  [Finnhub] institutional_ownership error for {symbol}: {e}")
        return []


def get_institutional_ownership_trends(symbol: str, years: int = 2) -> list[dict]:
    """Cached institutional ownership trend records for Phase E."""
    symbol = symbol.upper().strip()
    cached = read("institutional_ownership", symbol)
    if cached is not None:
        return cached
    trends = _fh_get_institutional_ownership_trends(symbol, years) if _fh_client else []
    if trends:
        write("institutional_ownership", symbol, trends)
    return trends


def _fh_get_patent_trends(symbol: str, years: int = 3) -> list[dict]:
    """USPTO patent activity from Finnhub, aggregated by year."""
    if not _fh_client:
        return []
    _fh_limiter.check()
    try:
        end = pd.Timestamp.now()
        start = end - pd.DateOffset(years=years)
        payload = _fh_client.stock_uspto_patent(
            symbol.upper(),
            _from=start.strftime("%Y-%m-%d"),
            to=end.strftime("%Y-%m-%d"),
        )
        _fh_limiter.record()
        return _as_records_by_period(
            _payload_rows(payload),
            date_keys=("filingDate", "publicationDate", "applicationDate", "date"),
            value_keys=(),
            granularity="year",
        )
    except RateLimitError:
        raise
    except Exception as e:
        print(f"  [Finnhub] stock_uspto_patent error for {symbol}: {e}")
        return []


def get_patent_trends(symbol: str, years: int = 3) -> list[dict]:
    """Cached patent activity trend records for Phase E."""
    symbol = symbol.upper().strip()
    cached = read("patents", symbol)
    if cached is not None:
        return cached
    trends = _fh_get_patent_trends(symbol, years) if _fh_client else []
    if trends:
        write("patents", symbol, trends)
    return trends


# ══════════════════════════════════════════════════════════════════════════════
# Diagnostics
# ══════════════════════════════════════════════════════════════════════════════

def rate_limit_status() -> list[dict]:
    """
    Current call-usage snapshot for all tracked providers.

    Example output:
        [
          {"provider": "Finnhub",      "window": "per-minute", "used": 12,  "limit": 60,  "resets_in": 44.2},
          {"provider": "Tiingo",       "window": "hourly",     "used": 8,   "limit": 50,  "resets_in": 1820.5},
          {"provider": "Tiingo",       "window": "daily",      "used": 31,  "limit": 500, "resets_in": 0.0},
          {"provider": "AlphaVantage", "window": "per-minute", "used": 3,   "limit": 5,   "resets_in": 22.8},
          {"provider": "AlphaVantage", "window": "daily",      "used": 9,   "limit": 25,  "resets_in": 0.0},
        ]
    """
    return _fh_limiter.status() + _tiingo_limiter.status() + _av_limiter.status()


# ══════════════════════════════════════════════════════════════════════════════
# Backwards-compatibility shims
# ══════════════════════════════════════════════════════════════════════════════
# Kept so that any module importing _fh_rate_limit or _av_rate_limit
# (e.g. EarningsRevision via the old alpha_vantage_client) doesn't break
# with AttributeError.  Migrate callers to RateLimiter instances when convenient.

def _fh_rate_limit() -> None:
    """Deprecated — use _fh_limiter.check() / .record() instead."""
    _fh_limiter.check()


def _av_rate_limit() -> None:
    """Deprecated — use _av_limiter.check() / .record() instead."""
    _av_limiter.check()
