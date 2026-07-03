"""
Screener: batch-scores the full US equity universe.

Threading strategy:
  Phase 1 — Cached stocks (no network):
    ThreadPoolExecutor(max_workers=16) — pure CPU, fully parallel.
    ~3,000 stocks cached → completes in a few seconds.

  Phase 2 — Uncached stocks (need SEC EDGAR fetch):
    ThreadPoolExecutor(max_workers=3) with a token-bucket rate limiter.
    Keeps SEC requests at ≤ 3/sec as a courtesy to the free API.

SEC allows ~10 req/sec. We use 3/sec to stay polite.
"""

import time
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..data import cache
from ..data import sec_data
from ..data import db
from ..models import graham
from ..models import quality
from . import scorer
from . import universe
from datetime import datetime, timezone



# ── Shared state ──────────────────────────────────────────────────────────────

_progress: dict = {
    "running":  False,
    "phase":    "",       # "cached" | "fetching" | ""
    "total":    0,
    "done":     0,
    "failed":   0,
    "current":  "",
    "results":  [],
}
_lock = threading.Lock()

# ── Per-user progress isolation (ISSUE-004) ───────────────────────────────────
# load_universe_background() and screener results (_progress) remain a shared
# singleton — universe/composite data is identical for every user. Only the
# per-session polling *view* is isolated here so concurrent users never read
# or clobber each other's last-seen progress snapshot.
_user_progress: dict[str, dict] = {}
_user_progress_lock = threading.Lock()
_USER_PROGRESS_TTL = 30 * 60  # seconds (ISSUE_014)
_USER_PROGRESS_TTL = 600  # seconds before stale per-session progress snapshots are evicted

# ── Rate limiter for SEC fetches (token-bucket, ≤ 3 calls/sec) ───────────────

_sec_rate_lock = threading.Lock()
_sec_last_call = 0.0
_SEC_MIN_GAP   = 0.34   # seconds between SEC requests


def _sec_rate_wait():
    """Block until it's safe to make the next SEC request."""
    global _sec_last_call
    with _sec_rate_lock:
        gap = _SEC_MIN_GAP - (time.time() - _sec_last_call)
        if gap > 0:
            time.sleep(gap)
        _sec_last_call = time.time()


# ── Progress accessors ────────────────────────────────────────────────────────

def _evict_stale_user_progress() -> None:
    import time as _t
    with _user_progress_lock:
        stale = [sid for sid, entry in _user_progress.items()
                 if _t.time() - entry.get("ts", 0) >= _USER_PROGRESS_TTL]
        for sid in stale:
            _user_progress.pop(sid, None)


def get_progress(session_id: str | None = None) -> dict:
    """
    Return the current (shared) background job progress.

    When ``session_id`` is provided, the returned snapshot is also stored in
    a per-user store (`_user_progress`) so each session polls its own
    isolated copy — preventing one user's poll from interfering with
    another's. The underlying job state itself remains a single shared
    singleton (universe loading is identical for all users).
    """
    _evict_stale_user_progress()
    with _lock:
        snapshot = dict(_progress)
    if session_id:
        with _user_progress_lock:
            _user_progress[session_id] = {"snapshot": snapshot, "ts": time.time()}
    return snapshot


def clear_user_progress(session_id: str) -> None:
    """Remove a user's isolated progress snapshot (e.g. on disconnect)."""
    with _user_progress_lock:
        _user_progress.pop(session_id, None)


def get_screener_results() -> list[dict]:
    """Return current results sorted by composite_score descending."""
    with _lock:
        return sorted(_progress["results"],
                      key=lambda x: x["composite_score"], reverse=True)

def _minimal_row(symbol: str, name: str = "", sector: str = "") -> dict:
    """Create a placeholder screener row before a stock has been analysed."""
    return {
        "symbol":          symbol,
        "name":            name or symbol,
        "sector":          sector,
        "graham_score":    0,
        "graham_max":      100,
        "graham_pct":      0,
        "quality_score":   0,
        "quality_max":     100,
        "quality_pct":     0,
        "composite_score": 0,
        "verdict":         "NOT_ANALYZED",
        "verdict_label":   "pending",
        "roe":             None,
        "op_margin":       None,
        "eps_years":       0,
        "div_years":       0,
        "graham_number":   None,
        "buffett_iv":      None,
        "market_cap":      None,
        "price":           None,
        "analyzed":        False,
        "updated_at":      None,
    }
# ── Score one stock ───────────────────────────────────────────────────────────

def _score_one(symbol: str) -> dict | None:
    """Score a single stock from cache or fresh fetch. Returns row dict or None."""
    try:
        cached_sec = cache.read("sec_facts", symbol)
        if not cached_sec:
            _sec_rate_wait()
            cached_sec = sec_data.fetch_company_facts(symbol)
            # Defer cache write to background thread (non-blocking)
            threading.Thread(
                target=cache.write, 
                args=("sec_facts", symbol, cached_sec),
                daemon=True
            ).start()

        g    = graham.score(None, cached_sec)
        q    = quality.score(cached_sec)
        comp = scorer.fundamental_only(g, q)

        return {
            "symbol":          symbol,
            "name":            cached_sec.get("name", symbol),
            "sector":          cached_sec.get("sector", "Unknown"),
            "graham_score":    g["total_score"],
            "graham_max":      g["total_max"],
            "graham_pct":      comp["graham_pct"],
            "quality_score":   q["total_score"],
            "quality_max":     q["total_max"],
            "quality_pct":     comp["quality_pct"],
            "composite_score": comp["composite_score"],
            "verdict":         comp["verdict"],
            "verdict_label":   comp["verdict_label"],
            "roe":             q.get("roe"),
            "op_margin":       q.get("op_margin"),
            "eps_years":       g.get("eps_years", 0),
            "div_years":       g.get("div_years", 0),
            # ── Enriched after full analysis ──────────────────────────────────
            "graham_number":   None,
            "buffett_iv":      None,
            "market_cap":      None,
            "price":           None,
            "analyzed":        False,
             "updated_at":      None,
        }
    except Exception:
        return None


# ── Update a row after full analysis (from app.analyze_stock) ─────────────────

def update_stock_after_analysis(symbol: str, analysis_result: dict) -> None:
    """
    Overwrite the screener row for `symbol` with accurate data from a full
    analysis (with live price).  Called from app.py after analyze_stock().

    Updates: graham_pct, quality_pct, composite_score, verdict, graham_number,
             price, market_cap, and sets analyzed=True.

    Also persists key metrics to the SQLite value_metrics store.
    """
    g        = analysis_result.get("graham",   {})
    q        = analysis_result.get("quality",  {})
    enhanced = analysis_result.get("enhanced", {})
    comp     = analysis_result.get("composite",{})
    b        = analysis_result.get("buffett",  {})

    g_pct      = enhanced.get("graham_pct")    or comp.get("graham_pct",    0)
    q_pct      = enhanced.get("quality_pct")   or comp.get("quality_pct",   0)
    composite  = enhanced.get("composite_score") or comp.get("composite_score", 0)
    verdict    = enhanced.get("verdict")       or comp.get("verdict",       "PENDING")
    vl         = enhanced.get("verdict_label") or comp.get("verdict_label", "pending")

    # $M — prefer top-level market_cap (live-price fallback computed in
    # app.analyze_stock); falls back to graham.score()'s value.
    mkt_cap       = analysis_result.get("market_cap") or g.get("market_cap")
    graham_number = g.get("graham_number")
    buffett_iv    = b.get("intrinsic_value")

    new_row_data = {
        "graham_pct":      round(g_pct, 1),
        "quality_pct":     round(q_pct, 1),
        "composite_score": round(composite, 1),
        "verdict":         verdict,
        "verdict_label":   vl,
        "graham_number":   graham_number,
        "buffett_iv":      buffett_iv,
        "market_cap":      mkt_cap,
        "price":           analysis_result.get("price"),
        "analyzed":        True,
         "updated_at":      datetime.now(timezone.utc).isoformat(),
    }

    with _lock:
        for i, row in enumerate(_progress["results"]):
            if row["symbol"] == symbol:
                _progress["results"][i] = {**row, **new_row_data}
                break
        else:
            _progress["results"].append({
                "symbol":          symbol,
                "name":            analysis_result.get("name",   symbol),
                "sector":          analysis_result.get("sector", "Unknown"),
                "graham_score":    g.get("total_score",    0),
                "graham_max":      g.get("total_max",     100),
                "quality_score":   q.get("total_score",    0),
                "quality_max":     q.get("total_max",     100),
                "roe":             None,
                "op_margin":       None,
                "eps_years":       0,
                "div_years":       0,
                **new_row_data,
            })

    # ── Persist to SQLite (non-blocking; failures are logged, not raised) ─────
    try:
        db.upsert(
            symbol,
            market_cap=mkt_cap,
            graham_number=graham_number,
            buffett_iv=buffett_iv,
            composite_score=round(composite, 1),
            verdict=verdict,
        )
    except Exception as e:
        print(f"  [DB] upsert failed for {symbol}: {e}")


# ── Background loader ─────────────────────────────────────────────────────────

def load_universe_background(tickers: list[str] | None = None):
    """
    Populate the screener with the full universe — no SEC fetches.
    Each row is a placeholder until the user runs a full analysis on the stock.
    Previously-analysed stocks are enriched from the local analysis cache.
    """
    with _lock:
        if _progress["running"]:
            return

    def _worker():
        symbols = tickers or universe.get_universe()

        try:
            ticker_map = sec_data.get_ticker_map()
        except Exception:
            ticker_map = {}

        with _lock:
            _progress.update({
                "running": True,
                "phase":   "loading",
                "total":   len(symbols),
                "done":    0,
                "failed":  0,
                "current": "Building universe…",
                "results": [],
            })

        # Build minimal placeholder rows — instant, no network calls
        rows = []
        for sym in symbols:
            entry = (ticker_map or {}).get(sym) or {}
            rows.append(_minimal_row(sym, name=entry.get("name", sym)))

        with _lock:
            _progress["results"] = rows
            _progress["done"]    = len(symbols)
            _progress["current"] = ""

        # Enrich with prior full-analysis results from cache
        _enrich_from_analysis_cache()
        _enrich_from_db()

        with _lock:
            _progress["results"].sort(
                key=lambda x: x.get("composite_score") or 0, reverse=True
            )
            _progress["running"] = False
            _progress["phase"]   = ""

        print(f"\n✅ Universe loaded: {len(symbols):,} tickers\n")

    threading.Thread(target=_worker, daemon=True).start()
# ── Enrich screener rows from persisted analysis cache ───────────────────────

def _enrich_from_analysis_cache() -> int:
    """
    After building base screener rows from SEC facts, scan the .cache directory
    for any previously-saved full analysis results (cache kind 'analysis') and
    apply the enriched fields (price, graham_number, buffett_iv, composite_score,
    verdict, etc.) to the matching rows in _progress["results"].

    This restores the post-analysis state of the screener table after a reboot
    so users don't lose the context of stocks they've already analysed.

    Returns the number of rows enriched.
    """
    analysis_symbols = cache.list_cached_kind("analysis")
    if not analysis_symbols:
        return 0

    # Build a fast lookup: symbol → row index
    with _lock:
        idx_map = {row["symbol"]: i for i, row in enumerate(_progress["results"])}

    enriched = 0
    for sym in analysis_symbols:
        data = cache.read("analysis", sym)
        if not data or "error" in data:
            continue

        g        = data.get("graham",   {}) or {}
        q        = data.get("quality",  {}) or {}
        enhanced = data.get("enhanced", {}) or {}
        comp     = data.get("composite",{}) or {}
        b        = data.get("buffett",  {}) or {}

        # Mirror the same logic as update_stock_after_analysis()
        g_pct     = enhanced.get("graham_pct")    or comp.get("graham_pct",    0)
        q_pct     = enhanced.get("quality_pct")   or comp.get("quality_pct",   0)
        composite = enhanced.get("composite_score") or comp.get("composite_score", 0)
        verdict   = enhanced.get("verdict")       or comp.get("verdict",       "PENDING")
        vl        = enhanced.get("verdict_label") or comp.get("verdict_label", "pending")
        entry = cache.read_entry("analysis", sym)
        updated_at = (
            datetime.fromtimestamp(entry["ts"], tz=timezone.utc).isoformat()
            if entry and entry.get("ts") else None
        )

        patch = {
            "graham_pct":      round(g_pct, 1),
            "quality_pct":     round(q_pct, 1),
            "composite_score": round(composite, 1),
            "verdict":         verdict,
            "verdict_label":   vl,
            "graham_number":   g.get("graham_number"),
            "buffett_iv":      b.get("intrinsic_value"),
            "market_cap":      data.get("market_cap") or g.get("market_cap"),
            "price":           data.get("price"),
            "analyzed":        True,
            "updated_at":      updated_at,
        }

        with _lock:
            i = idx_map.get(sym)
            if i is not None:
                _progress["results"][i] = {**_progress["results"][i], **patch}
            else:
                # Stock wasn't in universe cache — add a minimal row
                _progress["results"].append({
                    "symbol":          sym,
                    "name":            data.get("name",   sym),
                    "sector":          data.get("sector", "Unknown"),
                    "graham_score":    g.get("total_score",  0),
                    "graham_max":      g.get("total_max",  100),
                    "graham_pct":      round(g_pct, 1),
                    "quality_score":   q.get("total_score",  0),
                    "quality_max":     q.get("total_max",  100),
                    "quality_pct":     round(q_pct, 1),
                    "composite_score": round(composite, 1),
                    "verdict":         verdict,
                    "verdict_label":   vl,
                    "roe":             q.get("roe"),
                    "op_margin":       q.get("op_margin"),
                    "eps_years":       g.get("eps_years", 0),
                    "div_years":       g.get("div_years", 0),
                    "graham_number":   g.get("graham_number"),
                    "buffett_iv":      b.get("intrinsic_value"),
                    "market_cap":      data.get("market_cap") or g.get("market_cap"),
                    "price":           data.get("price"),
                    "analyzed":        True,
                    "updated_at":      updated_at,
                })
                idx_map[sym] = len(_progress["results"]) - 1
        enriched += 1

    if enriched:
        print(f"  ✅ Enriched {enriched} screener rows from analysis cache")
    return enriched


# ── Enrich screener rows from SQLite value_metrics store ─────────────────────

def _enrich_from_db() -> int:
    """
    Apply persisted value_metrics (market_cap, graham_number, buffett_iv,
    composite_score, verdict) to screener rows that have not yet been enriched
    by a full analysis in the current session.

    This is a fallback for rows whose JSON analysis cache has been cleared
    but whose SQLite row remains intact.

    Returns the number of rows enriched.
    """
    try:
        db_rows = db.get_all()
    except Exception as e:
        print(f"  [DB] get_all failed during enrichment: {e}")
        return 0

    if not db_rows:
        return 0

    with _lock:
        idx_map = {row["symbol"]: i for i, row in enumerate(_progress["results"])}

    enriched = 0
    for db_row in db_rows:
        sym = db_row["ticker"]
        with _lock:
            i = idx_map.get(sym)
            if i is None:
                continue
            existing = _progress["results"][i]
            # Only fill fields not already populated by a full analysis
            if existing.get("analyzed"):
                continue
            patch = {}
            if db_row.get("graham_number") is not None:
                patch["graham_number"] = db_row["graham_number"]
            if db_row.get("buffett_iv") is not None:
                patch["buffett_iv"] = db_row["buffett_iv"]
            if db_row.get("market_cap") is not None:
                patch["market_cap"] = db_row["market_cap"]
            if db_row.get("composite_score") is not None:
                patch["composite_score"] = db_row["composite_score"]
            if db_row.get("verdict") is not None:
                patch["verdict"] = db_row["verdict"]
                patch["analyzed"] = True
            if patch:
                _progress["results"][i] = {**existing, **patch}
                enriched += 1

    if enriched:
        print(f"  ✅ Enriched {enriched} screener rows from SQLite store")
    return enriched


# ── Load cached only (instant startup) ───────────────────────────────────────

def load_cached_only() -> list[dict]:
    """
    Build screener rows for the full universe instantly (no network).
    Enriches already-analysed stocks from the analysis cache and SQLite store.
    """
    symbols = universe.get_universe()
    if not symbols:
        return []

    try:
        ticker_map = sec_data.get_ticker_map()
    except Exception:
        ticker_map = {}

    rows = [
        _minimal_row(s, name=((ticker_map or {}).get(s) or {}).get("name", s))
        for s in symbols
    ]

    with _lock:
        _progress["results"] = rows

    _enrich_from_analysis_cache()
    _enrich_from_db()

    with _lock:
        _progress["results"].sort(
            key=lambda x: x.get("composite_score") or 0, reverse=True
        )

    n    = len(_progress["results"])
    n_db = db.count()
    print(f"  ✅ {n} stocks ready ({n_db} rows in SQLite store)")
    return _progress["results"]