"""
Screener: batch-scores the S&P 500 + S&P 400 universe.

Strategy:
  1. Load SEC data for all stocks (free, ~15 min first time, cached 6 months)
  2. Calculate Graham + Quality fundamentals (no price needed)
  3. Pre-rank by fundamental score
  4. Return results immediately; momentum added on individual stock view

SEC allows ~10 req/sec. We use 3/sec to be polite.
"""

import time
import threading
import traceback

import cache
import sec_data
import graham
import quality
import scorer
import universe

# Shared state for background loading progress
_progress = {
    "running":  False,
    "total":    0,
    "done":     0,
    "failed":   0,
    "current":  "",
    "results":  [],
}
_lock = threading.Lock()


def get_progress() -> dict:
    with _lock:
        return dict(_progress)


def get_screener_results() -> list[dict]:
    """Return current screener results, sorted by composite_score descending."""
    with _lock:
        return sorted(_progress["results"], key=lambda x: x["composite_score"], reverse=True)


def _score_one(symbol: str) -> dict | None:
    """Score a single stock from cache or fresh fetch. Returns row dict or None."""
    try:
        # Check cache
        cached_sec = cache.read("sec_facts", symbol)
        if not cached_sec:
            cached_sec = sec_data.fetch_company_facts(symbol)
            cache.write("sec_facts", symbol, cached_sec)

        # Graham
        g = graham.score(None, cached_sec)   # no price = no P/E, P/B

        # Quality
        q = quality.score(cached_sec)

        # Fundamental-only composite
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
            # Key metrics for table display
            "roe":             q.get("roe"),
            "op_margin":       q.get("op_margin"),
            "eps_years":       g.get("eps_years", 0),
            "div_years":       g.get("div_years", 0),
        }
    except Exception as e:
        return None


def load_universe_background(tickers: list[str] | None = None):
    """
    Kick off a background thread to load all stocks.
    Safe to call multiple times — no-ops if already running.
    """
    with _lock:
        if _progress["running"]:
            return  # already running

    def _worker():
        symbols = tickers or universe.get_universe()

        with _lock:
            _progress["running"] = True
            _progress["total"]   = len(symbols)
            _progress["done"]    = 0
            _progress["failed"]  = 0
            _progress["current"] = ""

        for symbol in symbols:
            with _lock:
                _progress["current"] = symbol

            row = _score_one(symbol)

            with _lock:
                _progress["done"] += 1
                if row:
                    # Remove old entry for this symbol if it exists
                    _progress["results"] = [
                        r for r in _progress["results"] if r["symbol"] != symbol
                    ]
                    _progress["results"].append(row)
                else:
                    _progress["failed"] += 1

            time.sleep(0.35)   # ~3 req/sec, polite to SEC

        with _lock:
            _progress["running"] = False
            _progress["current"] = ""
        print(f"\n✅ Screener complete: {_progress['done']} stocks scored, "
              f"{_progress['failed']} failed\n")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def load_cached_only() -> list[dict]:
    """
    Score only already-cached stocks (instant startup).
    Returns sorted results list.
    """
    symbols = universe.get_cached_universe()
    results = []
    for symbol in symbols:
        row = _score_one(symbol)
        if row:
            results.append(row)

    results.sort(key=lambda x: x["composite_score"], reverse=True)

    with _lock:
        _progress["results"] = results

    return results
