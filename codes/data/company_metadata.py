"""
Company Metadata Layer (ISSUE_001).

Decouples screener filter metadata (sector, industry, exchange) from the
lazy, per-user SEC analysis pipeline (sec_data.fetch_company_facts()).
"""

import os
import threading
import time

from . import cache, sec_data

_KIND = "company_meta"
_KEY = "map"
_REFRESH_STATE_KEY = "refresh_state"

_lock = threading.Lock()
_map: dict[str, dict] | None = None

_REFRESH_MIN_GAP = 0.34  # ~3/sec, matches screener.py's SEC rate limit
_REFRESH_COOLDOWN_SECONDS = 24 * 60 * 60
_refresh_lock = threading.Lock()
_refresh_last_call = 0.0
_refresh_running = False


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _metadata_backfill_enabled() -> bool:
    return _env_truthy("COMPANY_METADATA_BACKFILL_ENABLED")


def _refresh_cooldown_seconds() -> int:
    raw = os.environ.get("COMPANY_METADATA_BACKFILL_COOLDOWN_SECONDS")
    if raw is None:
        return _REFRESH_COOLDOWN_SECONDS
    try:
        return max(0, int(raw))
    except ValueError:
        return _REFRESH_COOLDOWN_SECONDS


def _refresh_on_cooldown(now: float | None = None) -> bool:
    state = cache.read(_KIND, _REFRESH_STATE_KEY) or {}
    last_started = state.get("started_at")
    if not last_started:
        return False
    now = time.time() if now is None else now
    return now - float(last_started) < _refresh_cooldown_seconds()


def _record_refresh_started(symbol_count: int, max_symbols: int) -> None:
    cache.write(_KIND, _REFRESH_STATE_KEY, {
        "started_at": time.time(),
        "symbol_count": symbol_count,
        "max_symbols": max_symbols,
    })


def _load() -> dict:
    global _map
    if _map is not None:
        return _map
    with _lock:
        if _map is not None:
            return _map
        _map = cache.read(_KIND, _KEY) or {}
        return _map


def _save() -> None:
    with _lock:
        cache.write(_KIND, _KEY, _map or {})


def get_metadata_map() -> dict:
    """Instant, network-free read of the current metadata cache."""
    return dict(_load())


def record_sector(symbol: str, sector: str, sic: int | None = None,
                   exchange: str | None = None) -> None:
    """Opportunistically record a symbol's sector — cheap, no extra network call."""
    if not symbol or not sector:
        return
    symbol = symbol.upper().strip()
    m = _load()
    entry = m.get(symbol, {})
    entry.update({
        "sector":   sector,
        "sic":      sic if sic is not None else entry.get("sic", 0),
        "exchange": exchange if exchange is not None else entry.get("exchange"),
        "updated":  time.time(),
    })
    m[symbol] = entry
    _save()


def enrich_rows(rows: list[dict]) -> int:
    """Fill missing 'sector' fields on screener rows from cache. No network."""
    m = _load()
    if not m:
        return 0
    n = 0
    for row in rows:
        if row.get("sector"):
            continue
        entry = m.get(row.get("symbol", ""))
        if entry and entry.get("sector"):
            row["sector"] = entry["sector"]
            n += 1
    return n


def _refresh_rate_wait() -> None:
    global _refresh_last_call
    with _refresh_lock:
        gap = _REFRESH_MIN_GAP - (time.time() - _refresh_last_call)
        if gap > 0:
            time.sleep(gap)
        _refresh_last_call = time.time()


def start_background_refresh(symbols: list[str], max_symbols: int = 2000,
                             *, force: bool = False) -> bool:
    """
    Fire-and-forget daemon thread backfilling sector metadata for symbols
    missing it, via the lightweight submissions-only fetch. Non-blocking.

    Large metadata backfills are opt-in for worker/scheduled contexts. Web
    processes should serve cached metadata instantly and record sectors
    opportunistically during normal analysis instead of spending SEC budget at
    startup.
    """
    global _refresh_running
    with _refresh_lock:
        if not force and not _metadata_backfill_enabled():
            return False
        if not force and _refresh_on_cooldown():
            return False
        if _refresh_running:
            return False
        _record_refresh_started(len(symbols), max_symbols)
        _refresh_running = True

    def _worker():
        global _refresh_running
        try:
            m = _load()
            missing = [s for s in symbols if s not in m or not m[s].get("sector")]
            missing = missing[:max_symbols]
            if not missing:
                return
            print(f"  [CompanyMetadata] backfilling sector for {len(missing)} symbols...")
            for i, sym in enumerate(missing, 1):
                _refresh_rate_wait()
                try:
                    info = sec_data.get_company_sector_light(sym)
                    if info.get("sector"):
                        record_sector(sym, info["sector"], info.get("sic"), info.get("exchange"))
                except Exception as e:
                    print(f"  [CompanyMetadata] ⚠️  {sym} failed: {e}")
                if i % 200 == 0:
                    print(f"  [CompanyMetadata] progress {i}/{len(missing)}")
            print(f"  [CompanyMetadata] ✅ backfill batch complete ({len(missing)} symbols)")
        finally:
            with _refresh_lock:
                _refresh_running = False

    threading.Thread(target=_worker, daemon=True).start()
    return True
