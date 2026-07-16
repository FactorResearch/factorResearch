"""Shared chart dataset preparation and caching."""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
import weakref
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from codes.core.redis_client import get_redis, json_get, json_set
from codes.data import db

DATA_VERSION = "market-v1"
CHART_SCHEMA_VERSION = "chart-schema-v1"
DEFAULT_PERIOD = "10y"
DEFAULT_TTL_SECONDS = 60 * 60 * 24
LOCK_TTL_SECONDS = 30
_LOCAL_MAX_ENTRIES = 256

_local_cache: OrderedDict[str, dict] = OrderedDict()
_local_locks = weakref.WeakValueDictionary()
_local_guard = threading.Lock()


@dataclass(frozen=True)
class ChartRequest:
    ticker: str
    chart_type: str
    period: str = DEFAULT_PERIOD
    data_version: str = DATA_VERSION
    analysis_version: str = "unknown"
    chart_schema_version: str = CHART_SCHEMA_VERSION
    config: dict[str, Any] | None = None


def normalized_config_hash(config: dict[str, Any] | None = None) -> str:
    """Return a deterministic, non-PII hash for chart configuration."""
    normalized = json.dumps(config or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def cache_key(request: ChartRequest) -> str:
    ticker = "".join(ch for ch in request.ticker.upper() if ch.isalnum() or ch in ".-")[:16]
    chart_type = "".join(ch for ch in request.chart_type.lower() if ch.isalnum() or ch in "_-")[:48]
    period = "".join(ch for ch in request.period.lower() if ch.isalnum() or ch in "_-")[:24]
    return ":".join([
        "chart",
        ticker,
        chart_type,
        period,
        request.data_version,
        request.analysis_version,
        request.chart_schema_version,
        normalized_config_hash(request.config),
    ])


def analysis_version_for(data: dict | None) -> str:
    """Derive an analysis-version token from persisted source data."""
    if not data:
        return "missing"
    for key in ("analysis_version", "data_version", "updated_at", "filing_date", "latest_filing"):
        value = data.get(key)
        if value:
            return str(value)
    digest_source = json.dumps(
        {
            "symbol": data.get("symbol"),
            "graham": data.get("graham", {}),
            "price_points": len(data.get("price_history") or []),
            "spy_points": len(data.get("spy_history") or []),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]


def get_analysis_chart_dataset(
    data: dict,
    chart_type: str,
    *,
    period: str = DEFAULT_PERIOD,
    config: dict[str, Any] | None = None,
) -> dict:
    ticker = str(data.get("symbol") or (config or {}).get("symbol") or "")
    request = ChartRequest(
        ticker=ticker,
        chart_type=chart_type,
        period=period,
        analysis_version=analysis_version_for(data),
        config=config,
    )
    return get_chart_dataset(request, lambda: _build_analysis_dataset(data, chart_type))


def get_composite_trend_dataset(
    symbol: str,
    *,
    limit: int = 90,
    period: str = DEFAULT_PERIOD,
    config: dict[str, Any] | None = None,
) -> dict:
    request = ChartRequest(
        ticker=symbol,
        chart_type="composite_trend",
        period=period,
        analysis_version=f"snapshots-{int(limit)}",
        config={**(config or {}), "limit": int(limit)},
    )
    return get_chart_dataset(request, lambda: _build_composite_trend_dataset(symbol, limit=limit))


def get_chart_dataset(request: ChartRequest, builder: Callable[[], dict], *, ttl: int = DEFAULT_TTL_SECONDS) -> dict:
    key = cache_key(request)
    started = time.perf_counter()

    cached = _read_shared(key)
    if cached is not None:
        return _with_meta(cached, key=key, cache_hit=True, started=started)

    if _with_redis_generation_lock(key):
        cached = _read_shared(key)
        if cached is not None:
            return _with_meta(cached, key=key, cache_hit=True, started=started)

    lock = _get_local_lock(key)
    with lock:
        cached = _read_shared(key)
        if cached is not None:
            return _with_meta(cached, key=key, cache_hit=True, started=started)

        try:
            payload = builder()
        except Exception as exc:
            payload = {"error": type(exc).__name__, "series": []}
        stored = {
            "request": request.__dict__,
            "dataset": payload,
            "generated_at": time.time(),
        }
        _write_shared(key, stored, ttl=ttl)
        return _with_meta(stored, key=key, cache_hit=False, started=started)


def _with_redis_generation_lock(key: str) -> bool:
    r = get_redis()
    if not r:
        return False
    lock_key = f"{key}:lock"
    token = str(time.time())
    try:
        acquired = r.set(lock_key, token, nx=True, ex=LOCK_TTL_SECONDS)
    except Exception:
        return False
    if acquired:
        return False

    deadline = time.time() + 2.0
    while time.time() < deadline:
        time.sleep(0.05)
        if _read_shared(key) is not None:
            return True
    return False


def _with_meta(payload: dict, *, key: str, cache_hit: bool, started: float) -> dict:
    result = copy.deepcopy(payload.get("dataset", {}))
    result["meta"] = {
        "cache_key": key,
        "cache_hit": cache_hit,
        "generated_at": payload.get("generated_at"),
        "generation_ms": round((time.perf_counter() - started) * 1000, 3),
    }
    return result


def _build_analysis_dataset(data: dict, chart_type: str) -> dict:
    if chart_type == "eps_history":
        return _eps_dataset((data.get("graham") or {}).get("eps_history") or [], str(data.get("symbol") or ""))
    if chart_type == "price_history":
        return _price_dataset(data.get("price_history"), data.get("spy_history"), str(data.get("symbol") or ""))
    if chart_type == "dividend_history":
        return _dividend_dataset((data.get("graham") or {}).get("div_history") or [], str(data.get("symbol") or ""))
    raise ValueError(f"Unknown analysis chart type: {chart_type}")


def _eps_dataset(eps_history: list, symbol: str) -> dict:
    if not eps_history:
        return {"empty": "No EPS data", "series": []}
    df = pd.DataFrame(eps_history).sort_values("year")
    values = pd.to_numeric(df["value"], errors="coerce")
    return {
        "title": f"{symbol} EPS History (10yr)",
        "series": [{
            "type": "bar",
            "x": df["year"].astype(str).tolist(),
            "y": values.where(pd.notna(values), None).tolist(),
        }],
    }


def _price_dataset(price_history_dict, spy_history_dict, symbol: str) -> dict:
    hist = _normalised_price_series(price_history_dict)
    spy_hist = _normalised_price_series(spy_history_dict)
    if not hist:
        return {"empty": "No price data", "series": []}
    series = [{"name": symbol, "x": [row["Date"] for row in hist], "y": [row["norm"] for row in hist]}]
    if spy_hist:
        series.append({"name": "SPY", "x": [row["Date"] for row in spy_hist], "y": [row["norm"] for row in spy_hist]})
    return {"title": f"{symbol} vs SPY (10yr normalised)", "series": series}


def _dividend_dataset(div_history: list, symbol: str) -> dict:
    if not div_history:
        return {"empty": "No dividends", "series": []}
    df = pd.DataFrame(div_history).sort_values("year")
    values = pd.to_numeric(df["value"], errors="coerce")
    df = df[values > 0]
    values = pd.to_numeric(df["value"], errors="coerce")
    if df.empty:
        return {"empty": "No dividends", "series": []}
    return {
        "title": f"{symbol} Dividend Payments (USD Millions)",
        "series": [{
            "type": "bar",
            "x": df["year"].astype(str).tolist(),
            "y": (values / 1e6).where(pd.notna(values), None).tolist(),
            "raw_y": values.where(pd.notna(values), None).tolist(),
        }],
    }


def _normalised_price_series(rows) -> list[dict]:
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    if df.empty or "Close" not in df or "Date" not in df:
        return []
    df = df.copy()
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"])
    if df.empty or float(df["Close"].iloc[0]) <= 0:
        return []
    df["norm"] = df["Close"] / float(df["Close"].iloc[0]) * 100
    return df[["Date", "norm"]].to_dict("records")


def _build_composite_trend_dataset(symbol: str, *, limit: int = 90) -> dict:
    try:
        history = db.list_composite_score_history(symbol, limit=limit)
    except Exception as exc:
        return {"error": str(exc), "series": []}
    if len(history) < 2:
        return {"empty": "Composite trend will appear after the next score update.", "series": []}
    return {
        "series": [{
            "name": "Composite",
            "x": [row["snapshot_date"] for row in history],
            "y": [row["composite_score"] for row in history],
        }],
    }


def _read_shared(key: str) -> dict | None:
    r = get_redis()
    if r:
        return json_get(r, key)
    with _local_guard:
        entry = _local_cache.get(key)
        if entry is not None:
            _local_cache.move_to_end(key)
            return copy.deepcopy(entry)
    return None


def _write_shared(key: str, payload: dict, *, ttl: int) -> None:
    r = get_redis()
    if r:
        json_set(r, key, payload, ex=ttl)
        return
    with _local_guard:
        _local_cache[key] = copy.deepcopy(payload)
        _local_cache.move_to_end(key)
        while len(_local_cache) > _LOCAL_MAX_ENTRIES:
            _local_cache.popitem(last=False)


def _get_local_lock(key: str) -> threading.Lock:
    with _local_guard:
        lock = _local_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _local_locks[key] = lock
        return lock


def clear_local_cache() -> None:
    with _local_guard:
        _local_cache.clear()
        _local_locks.clear()
