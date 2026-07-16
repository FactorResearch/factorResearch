import time
import datetime as dt

from codes.core.ports import TickerUniverseReader
from codes.data.providers.sec_universe import SecTickerUniverseAdapter

from ..data import cache
from ..data import sec_data
from ..data import temporal

# ISSUE_003: rate gap for the eligibility sweep — matches the existing
# ~3 req/sec convention used by screener.py / sec_refresh_worker.py.
_SEC_MIN_GAP = 0.34

# =========================
# SEC company_tickers.json
# =========================

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


def _fetch_sec_tickers(reader: TickerUniverseReader | None = None) -> list[str]:
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
        tickers = list((reader or SecTickerUniverseAdapter()).read_tickers())

        print(f"✅ Loaded {len(tickers):,} SEC tickers")

        return tickers

    except Exception as exc:
        print(f"⚠️ Failed to load SEC universe: {exc}")
        print("⚠️ Falling back to default ticker list.")
        return FALLBACK_TICKERS


def get_universe(reader: TickerUniverseReader | None = None) -> list[str]:
    """
    Return the full SEC company universe.
    """
    cached = cache.read("universe", "sec_all")

    if cached:
        return cached

    universe = _fetch_sec_tickers(reader)

    if universe:
        cache.write("universe", "sec_all", universe)

    return universe


def get_universe_as_of(code: str, as_of: dt.date) -> list[str]:
    """Return a sourced historical universe without a current-membership fallback."""
    return [row["symbol"] for row in temporal.get_universe_members(code, as_of) if row.get("symbol")]


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


# =========================
# ISSUE_003: Validated Graham-eligible universe
# =========================
#
# Eliminates unnecessary SEC CompanyFacts downloads for ETFs, mutual
# funds, trusts, SPACs, and other non-operating entities by classifying
# each ticker's filer type BEFORE any CompanyFacts fetch occurs.
#
# Eligibility source: sec_data._filing_type(), which inspects the SAME
# lightweight /submissions/ payload the worker already fetches for its
# "latest filing date" staleness check — this adds no new API surface,
# only reorders when the existing submissions call happens (once here,
# during universe validation, instead of only inside fetch_company_facts).
#
# Filer types (see sec_data._filing_type docstring):
#   "us"       -> files 10-K/10-Q                    -> ELIGIBLE
#   "foreign"  -> files 20-F/40-F                     -> ELIGIBLE
#   "adr_only" -> files only F-6 (no financials)       -> excluded
#   "none"     -> no matching forms (funds/trusts/etc) -> excluded
#
# No name-based heuristics ("Fund", "Trust", "ETF") are used, per the
# issue's constraints — classification is entirely form-type driven.

def _build_eligible_universe(tickers: list[str]) -> list[str]:
    """
    Classify each ticker via sec_data._filing_type() and return only the
    operating-company subset ("us" | "foreign" filer types).

    Rate-limited to ~3 req/sec (SEC courtesy limit, matches the existing
    convention in screener.py / sec_refresh_worker.py). This is a slow,
    one-time-ish sweep over the full raw universe — callers should use
    get_graham_eligible_universe() which caches the result rather than
    calling this directly on every run.
    """
    eligible: list[str] = []
    last_call = [0.0]

    for i, ticker in enumerate(tickers, 1):
        try:
            cik, _name = sec_data.get_cik(ticker)
        except ValueError:
            continue  # not in SEC ticker map — can't classify, skip

        gap = _SEC_MIN_GAP - (time.time() - last_call[0])
        if gap > 0:
            time.sleep(gap)
        last_call[0] = time.time()

        try:
            subs = sec_data._fetch_submissions(cik)
        except Exception as e:
            print(f"  [Universe] ⚠️  {ticker} submissions fetch failed: {e}")
            continue

        filer = sec_data._filing_type(subs)
        if filer in ("us", "foreign"):
            eligible.append(ticker)

        if i % 200 == 0:
            print(f"  [Universe] eligibility sweep {i}/{len(tickers)} "
                  f"({len(eligible)} eligible so far)")

    return eligible


def get_graham_eligible_universe(force_refresh: bool = False) -> list[str]:
    """
    Return the validated Graham-eligible universe: SEC reporting companies
    that file standard operating-company forms (10-K/10-Q or 20-F/40-F).

    Excludes ETFs, mutual funds, trusts, SPACs, shell companies, and
    ADR-only filers — determined purely by filed form types via
    sec_data._filing_type(), never by company-name keywords.

    Cached under a separate key ("sec_eligible") from the raw universe
    ("sec_all") so it can be refreshed independently on demand via
    force_refresh=True, without needing to re-fetch the raw SEC ticker
    list or touch the SEC CompanyFacts cache.

    codes/workers/sec_refresh_worker.py should call this instead of
    get_universe() so it never downloads CompanyFacts for ineligible
    tickers (e.g. BRK.B remains eligible — it's a standard 10-K filer).
    """
    if not force_refresh:
        cached = cache.read("universe", "sec_eligible")
        if cached:
            return cached

    raw = get_universe()
    print(f"  [Universe] building Graham-eligible universe from "
          f"{len(raw):,} raw tickers (rate-limited SEC sweep)...")
    eligible = _build_eligible_universe(raw)

    if eligible:
        cache.write("universe", "sec_eligible", eligible)

    print(f"✅ Graham-eligible universe: {len(eligible):,}/{len(raw):,} tickers")
    return eligible
