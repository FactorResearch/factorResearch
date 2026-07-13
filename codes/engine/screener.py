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
from ..core.redis_client import get_redis, json_get, json_set
from ..data import cache
from ..data import sec_data
from ..data import db
from ..models import graham
from ..models import quality
from . import scorer
from . import universe
from datetime import datetime, timezone
from ..data import company_metadata
from codes import security

_PROGRESS_REDIS_KEY = "screener:progress"


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

def _sync_progress_to_redis() -> None:
    r = get_redis()
    if not r:
        return
    with _lock:
        snapshot = dict(_progress)
    json_set(r, _PROGRESS_REDIS_KEY, snapshot)
def get_progress(session_id: str | None = None) -> dict:
    _evict_stale_user_progress()
    r = get_redis()
    if r:
        remote = json_get(r, _PROGRESS_REDIS_KEY)
        if remote is not None:
            with _lock:
                _progress.update(remote)
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
def get_sector_avg_return_12m(sector: str, exclude_symbol: str | None = None) -> float | None:
    """Mean skip-month 12M return across analyzed peers in the same sector."""
    with _lock:
        rows = [
            r for r in _progress["results"]
            if r.get("sector") == sector
            and r.get("analyzed")
            and r.get("return_12m") is not None
            and r.get("symbol") != exclude_symbol
        ]
    if not rows:
        return None
    return sum(r["return_12m"] for r in rows) / len(rows)

def _minimal_row(
    symbol: str,
    name: str = "",
    sector: str = "",
    *,
    market_code: str = "US",
) -> dict:
    """Create a placeholder screener row before a stock has been analysed."""
    return {
        "market_code":      market_code.upper(),
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
        cached_sec = db.get_sec_facts(symbol)
        if not cached_sec:
            return None   # not yet populated by the worker — skip for now

        g    = graham.score(None, cached_sec)
        q    = quality.score(cached_sec)
        comp = scorer.fundamental_only(g, q)

        return {
            "market_code":      "US",
            "symbol":          symbol,
            "name":            security.sanitize_string(cached_sec.get("name", symbol), max_length=200) if cached_sec.get("name") else symbol,
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

def get_sector_avg_momentum(sector: str, exclude_symbol: str | None = None) -> float | None:
    """
    Live-computed peer-sector average 12M (skip-month) return, from
    currently cached analyses only (ISSUE 19.2C). No pre-aggregation —
    recomputed fresh on every call per user's requested behavior.
    """
    if not sector:
        return None
    rets = []
    for sym in db.list_analysis_tickers():
        if sym == exclude_symbol:
            continue
        data = db.get_analysis(sym)
        if not data or data.get("sector") != sector:
            continue
        r = (data.get("momentum") or {}).get("return_12m")
        if r is not None:
            rets.append(r)
    return sum(rets) / len(rets) if rets else None
# ── Update a row after full analysis (from app.analyze_stock) ─────────────────

def update_stock_after_analysis(symbol: str, analysis_result: dict) -> None:
    """
    Overwrite the screener row for `symbol` with accurate data from a full
    analysis (with live price).  Called from app.py after analyze_stock().

    Updates: graham_pct, quality_pct, composite_score, verdict, graham_number,
             price, market_cap, and sets analyzed=True.

    Also persists key metrics to the market database.
    """
    g        = analysis_result.get("graham",   {})
    q        = analysis_result.get("quality",  {})
    enhanced = analysis_result.get("enhanced", {})
    comp     = analysis_result.get("composite",{})
    b        = analysis_result.get("buffett",  {})
    sector_val = analysis_result.get("sector")
    if sector_val:
        company_metadata.record_sector(symbol, sector_val)

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
        "market_code":      str(analysis_result.get("market_code") or "US").upper(),
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
        "return_12m": (analysis_result.get("momentum") or {}).get("return_12m"),
    }

    with _lock:
        for i, row in enumerate(_progress["results"]):
            if (
                row["symbol"] == symbol
                and str(row.get("market_code") or "US").upper() == new_row_data["market_code"]
            ):
                _progress["results"][i] = {**row, **new_row_data}
                break
        else:
            _progress["results"].append({
                "market_code":      new_row_data["market_code"],
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

    # Persist to Postgres (non-blocking; failures are logged, not raised).
    try:
        _sync_progress_to_redis()
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
    Populate the screener from an explicit ticker list — no SEC fetches.
    Each row is a placeholder until the user runs a full analysis on the stock.
    Previously-analysed stocks are enriched from the local analysis cache.
    """
    if tickers is None:
        raise RuntimeError("Full-universe loading is disabled; pass an explicit ticker list.")

    with _lock:
        if _progress["running"]:
            return

    def _worker():
        symbols = tickers

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
            rows.append(_minimal_row(sym, name=entry.get("name", sym), market_code="US"))

        with _lock:
            _progress["results"] = rows
            _progress["done"]    = len(symbols)
            _progress["current"] = ""

        # Enrich with prior full-analysis results from cache
        _enrich_from_analysis_cache()
        _enrich_from_db()
        company_metadata.start_background_refresh(symbols)
        _merge_persisted_market_screener_rows(backfill=True)

        with _lock:
            _progress["results"].sort(
                key=lambda x: x.get("composite_score") or 0, reverse=True
            )
            _progress["running"] = False
            _progress["phase"]   = ""
        _sync_progress_to_redis()
        # ISSUE_001: instant, network-free sector fill from metadata cache
        with _lock:
            company_metadata.enrich_rows(_progress["results"])

        print(f"\n✅ Universe loaded: {len(symbols):,} tickers\n")
    
    threading.Thread(target=_worker, daemon=True).start()
# ── Enrich screener rows from persisted analysis cache ───────────────────────

def _enrich_from_analysis_cache() -> int:
    analysis_symbols = db.list_analysis_tickers()
    if not analysis_symbols:
        return 0

    with _lock:
        idx_map = {
            (str(row.get("market_code") or "US").upper(), row["symbol"]): i
            for i, row in enumerate(_progress["results"])
        }

    enriched = 0
    for sym in analysis_symbols:
        entry = db.get_analysis_entry(sym)
        if not entry:
            continue
        data = entry["data"]
        if not data or "error" in data:
            continue

        g        = data.get("graham",   {}) or {}
        q        = data.get("quality",  {}) or {}
        enhanced = data.get("enhanced", {}) or {}
        comp     = data.get("composite",{}) or {}
        b        = data.get("buffett",  {}) or {}

        g_pct     = enhanced.get("graham_pct")    or comp.get("graham_pct",    0)
        q_pct     = enhanced.get("quality_pct")   or comp.get("quality_pct",   0)
        composite = enhanced.get("composite_score") or comp.get("composite_score", 0)
        verdict   = enhanced.get("verdict")       or comp.get("verdict",       "PENDING")
        vl        = enhanced.get("verdict_label") or comp.get("verdict_label", "pending")
        updated_at = entry.get("updated_at")

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
            i = idx_map.get(("US", sym))
            if i is not None:
                _progress["results"][i] = {**_progress["results"][i], **patch}
            else:
                _progress["results"].append({
                    "market_code":      "US",
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
                idx_map[("US", sym)] = len(_progress["results"]) - 1
        enriched += 1

    if enriched:
        print(f"  ✅ Enriched {enriched} screener rows from analysis DB")
    return enriched
# ── Enrich U.S. screener rows from persisted value_metrics ───────────────────

def _enrich_from_db() -> int:
    """
    Apply persisted value_metrics (market_cap, graham_number, buffett_iv,
    composite_score, verdict) to screener rows that have not yet been enriched
    by a full analysis in the current session.

    This is a fallback for rows whose analysis cache has been cleared but whose
    relational value_metrics row remains intact.

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
        idx_map = {
            (str(row.get("market_code") or "US").upper(), row["symbol"]): i
            for i, row in enumerate(_progress["results"])
        }

    enriched = 0
    for db_row in db_rows:
        sym = db_row["ticker"]
        with _lock:
            i = idx_map.get(("US", sym))
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
        print(f"  ✅ Enriched {enriched} screener rows from market DB")
    return enriched


def _merge_persisted_market_screener_rows(*, backfill: bool = False) -> int:
    """Merge enabled non-SEC market projections into shared screener state."""
    try:
        from codes.data.providers.registry import (
            backfill_enabled_market_screener_projections,
            configured_market_codes,
        )

        if backfill:
            stats = backfill_enabled_market_screener_projections()
            if stats["created"]:
                print(
                    f"  ✅ Backfilled {stats['created']} market screener "
                    "projection(s) from existing verified facts"
                )
        market_codes = configured_market_codes()
        persisted = db.get_market_screener_rows(market_codes)
    except Exception as exc:
        print(f"  [Market screener] load failed: {exc}")
        return 0

    with _lock:
        index = {
            (str(row.get("market_code") or "US").upper(), row["symbol"]): i
            for i, row in enumerate(_progress["results"])
        }
        for persisted_row in persisted:
            market_code = str(persisted_row.get("market_code") or "").upper()
            symbol = str(persisted_row.get("symbol") or "").upper()
            if not market_code or not symbol:
                continue
            normalized = {
                **_minimal_row(
                    symbol,
                    name=persisted_row.get("name") or symbol,
                    sector=persisted_row.get("sector") or "Unknown",
                    market_code=market_code,
                ),
                **persisted_row,
                "market_code": market_code,
                "symbol": symbol,
                "name": persisted_row.get("name") or symbol,
                "sector": persisted_row.get("sector") or "Unknown",
            }
            key = (market_code, symbol)
            existing_index = index.get(key)
            if existing_index is None:
                _progress["results"].append(normalized)
                index[key] = len(_progress["results"]) - 1
            elif not _progress["results"][existing_index].get("analyzed"):
                _progress["results"][existing_index] = {
                    **_progress["results"][existing_index],
                    **normalized,
                }
    return len(persisted)


# ── Load cached only (instant startup) ───────────────────────────────────────

def load_cached_only() -> list[dict]:
    """
    Build screener rows for the full universe instantly (no network).
    Enriches U.S. rows and merges verified projections for enabled markets.
    """
    symbols = universe.get_universe() or []

    ticker_map = {}
    if symbols:
        try:
            ticker_map = sec_data.get_ticker_map()
        except Exception:
            ticker_map = {}

    rows = [
        _minimal_row(
            s,
            name=((ticker_map or {}).get(s) or {}).get("name", s),
            market_code="US",
        )
        for s in symbols
    ]

    with _lock:
        _progress["results"] = rows

    if symbols:
        _enrich_from_analysis_cache()
        _enrich_from_db()
        company_metadata.enrich_rows(_progress["results"])

    _merge_persisted_market_screener_rows(backfill=True)

    with _lock:
        _progress["results"].sort(
            key=lambda x: x.get("composite_score") or 0, reverse=True
        )

    n    = len(_progress["results"])
    try:
        n_db = db.count()
    except Exception:
        n_db = 0
    print(f"  ✅ {n} stocks ready ({n_db} value rows in market DB)")
    _sync_progress_to_redis()
    return _progress["results"]
