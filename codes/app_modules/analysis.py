"""Stock analysis pipeline and analysis-level caches."""

import os
import threading
import time as _time
import datetime as _datetime
from concurrent.futures import ThreadPoolExecutor

from codes import security
from codes.core import singleflight
from codes.core.model_registry import MODELS
from codes.data import api_fetcher, sec_data, db, market_data
from codes.data.api_fetcher import RateLimitError
from codes.data.providers.registry import require_symbol_market_enabled, scoring_facts_for_symbol
from codes.engine import factor_engine, scorer, screener, market_fear
from codes.models import (
    graham, quality, momentum, piotroski, altman, risk_metrics, greenblatt,
    buffett, earnings_revision, profitability as profitability_model,
    fcf_quality as fcf_quality_model, capital_allocation as capital_allocation_model,
    growth_quality as growth_quality_model, regime as regime_model,
    insider_activity as insider_activity_model, factor_momentum as factor_momentum_model,
    alternative_data as alternative_data_model,
    spy_benchmark_model, bias_engine, comomentum as comomentum_model,
)
from codes.models.analysis_snapshot import AnalysisType
from codes.services.analysis_snapshot_service import save_standard_snapshot
from codes.services import performance_metrics
from codes.services import provider_gateway
from codes.services import component_cache
from codes.services import analysis_jobs

from .config import validate_ticker

# ── Performance Optimization: Module-level caches ─────────────────────────────
_spy_history = None
_spy_history_loaded = False
_spy_history_ts = 0.0
_spy_history_lock = threading.Lock()
_analysis_cache = {}
_analysis_cache_lock = threading.Lock()
_comomentum_cache = {"ts": 0.0, "result": None, "loaded": False}
_comomentum_lock = threading.Lock()
_market_fear_cache = {"ts": 0.0, "result": None, "loaded": False}
_market_fear_lock = threading.Lock()
_COMOMENTUM_TTL = 3600  # seconds
_COMOMENTUM_TOP_N = 20
_MARKET_FEAR_TTL = 3600  # seconds
ANALYSIS_VERSION = "2026.07-opt1"
ANALYSIS_MAX_AGE_SECONDS = int(os.environ.get("ANALYSIS_MAX_AGE_SECONDS", 30 * 86400))
_MODEL_VERSIONS = {key: model.version for key, model in MODELS.items()}


def _timed(timings: dict[str, float], name: str, callback):
    started = _time.perf_counter()
    try:
        return callback()
    finally:
        timings[name] = round((_time.perf_counter() - started) * 1000, 2)


def _component(timings: dict[str, float], name: str, symbol: str, inputs, callback):
    started = _time.perf_counter()
    result, cache_hit = component_cache.get_or_compute(
        name, symbol, _MODEL_VERSIONS[name], inputs, callback,
    )
    timings[name] = round((_time.perf_counter() - started) * 1000, 2)
    timings[f"{name}_cache_hit"] = cache_hit
    return result


def _get_spy_history_lazy():
    """Fetch SPY history once at startup, cache it module-level. Subsequent calls are instant."""
    global _spy_history, _spy_history_loaded, _spy_history_ts
    now = _time.time()
    if _spy_history_loaded and (_spy_history is not None or now - _spy_history_ts < _MARKET_FEAR_TTL):
        return _spy_history
    
    with _spy_history_lock:
        if _spy_history_loaded and (_spy_history is not None or now - _spy_history_ts < _MARKET_FEAR_TTL):
            return _spy_history
        try:
            _spy_history = api_fetcher.get_price_history("SPY", years=10)
        except Exception as e:
            print(f"Failed to fetch SPY history: {e}")
            _spy_history = None
        _spy_history_loaded = True
        _spy_history_ts = now
        return _spy_history
def _is_rate_limit_error(exc: Exception) -> bool:
    """Recognize RateLimitError instances across import aliases."""
    if isinstance(exc, RateLimitError):
        return True
    return type(exc).__name__ == "RateLimitError"
def _get_comomentum_result() -> dict | None:
    """Top-momentum basket co-movement, recomputed at most once per hour."""
    global _comomentum_cache
    now = _time.time()
    with _comomentum_lock:
        if _comomentum_cache["loaded"] and now - _comomentum_cache["ts"] < _COMOMENTUM_TTL:
            return _comomentum_cache["result"]

    try:
        results = screener.get_screener_results()
        candidates = [
            (r["symbol"], r["return_12m"]) for r in results
            if r.get("analyzed") and r.get("return_12m") is not None
        ]
        top_symbols = [symbol for symbol, _return in sorted(candidates, key=lambda item: item[1], reverse=True)[:_COMOMENTUM_TOP_N]]
        result = None
        if len(top_symbols) >= 2:
            price_histories = {}
            workers = min(int(os.environ.get("COMOMENTUM_WORKERS", "4")), len(top_symbols))
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="comomentum") as executor:
                histories = {sym: executor.submit(api_fetcher.get_price_history, sym, 3) for sym in top_symbols}
            for sym, future in histories.items():
                try:
                    h = future.result()
                    if h is not None and not h.empty:
                        price_histories[sym] = h
                except Exception as e:
                    print(f"Comomentum: history fetch failed for {sym}: {e}")

            result = comomentum_model.calc_comomentum(top_symbols, price_histories)
    except Exception as e:
        print(f"Comomentum calculation failed: {e}")
        result = None

    with _comomentum_lock:
        _comomentum_cache = {"ts": now, "result": result, "loaded": True}
    return result


def _get_market_fear_result() -> dict | None:
    """Current VIX/VIXEQ fear gauge, recomputed at most once per hour."""
    global _market_fear_cache
    now = _time.time()
    with _market_fear_lock:
        if _market_fear_cache["loaded"] and now - _market_fear_cache["ts"] < _MARKET_FEAR_TTL:
            return _market_fear_cache["result"]

    try:
        inputs = market_data.get_market_fear_inputs()
        result = market_fear.analyze(
            inputs.get("vix"),
            inputs.get("vixeq"),
            spread_history=inputs.get("spread_history"),
        )
    except Exception as e:
        print(f"Market fear gauge failed: {e}")
        result = None

    with _market_fear_lock:
        _market_fear_cache = {"ts": now, "result": result, "loaded": True}
    return result


def _attach_market_fear(result: dict) -> dict:
    if result and "error" not in result:
        result["market_fear"] = _get_market_fear_result()
    return result


def is_production() -> bool:
    
    return os.environ.get("FLASK_ENV", "").lower() == "production"


def _set_cache_metadata(result: dict, cache_hit: bool, cache_source: str) -> dict:
    if isinstance(result, dict):
        result["cache_hit"] = cache_hit
        result["cache_source"] = cache_source
        result["cache_stale"] = not _cache_is_current(result) if cache_hit else False
    return result


def _cache_is_current(result: dict) -> bool:
    if result.get("analysis_version") != ANALYSIS_VERSION:
        return False
    generated_at = result.get("generated_at")
    if not generated_at:
        return False
    try:
        age = _time.time() - _datetime.datetime.fromisoformat(generated_at).timestamp()
    except (TypeError, ValueError):
        return False
    return age < ANALYSIS_MAX_AGE_SECONDS


def _analyze_stock(symbol: str, *, force_refresh: bool = False, defer_secondary: bool = False) -> dict:
    """Full pipeline: SEC → Graham + Quality + (Price→Momentum) → Composite.
    
    Optimizations:
    - 1A: In-memory cache for repeat lookups
    - 1G: Eliminate redundant graham.score(None, ...) call
    - 1B: Parallelize network fetches with ThreadPoolExecutor
    - 1C: Lazy-load SPY history once, reuse across all stocks
    """
    global _analysis_cache, _analysis_cache_lock
    analysis_started = _time.perf_counter()
    timings: dict[str, float] = {}

    symbol = validate_ticker(symbol)
    if not symbol:
        return {"error": "Invalid ticker format."}
    try:
        require_symbol_market_enabled(symbol)
    except ValueError as exc:
        return {"error": str(exc)}
    # 1A: Check in-memory cache first (zero disk I/O for repeat lookups)
    with _analysis_cache_lock:
        if not force_refresh and symbol in _analysis_cache:
            cached_memory = _set_cache_metadata(_analysis_cache[symbol], True, "memory")
            _attach_market_fear(cached_memory)
            try:
                save_standard_snapshot(cached_memory, analysis_type=AnalysisType.STANDARD)
            except Exception as e:
                print(f"Analysis snapshot save failed for {symbol}: {type(e).__name__}: {e}")
            performance_metrics.record_analysis((_time.perf_counter() - analysis_started) * 1000, True)
            return cached_memory
    # Then try disk cache
    cached = None if force_refresh else db.get_analysis(symbol)

    if cached:
        _set_cache_metadata(cached, True, "database")
        _attach_market_fear(cached)
        try:
            save_standard_snapshot(cached, analysis_type=AnalysisType.STANDARD)
        except Exception as e:
            print(f"Analysis snapshot save failed for {symbol}: {type(e).__name__}: {e}")
        with _analysis_cache_lock:
            _analysis_cache[symbol] = cached
        performance_metrics.record_analysis((_time.perf_counter() - analysis_started) * 1000, True)
        return cached
    # International symbols read verified normalized facts from the market DB;
    # U.S. symbols retain the existing SEC-only path.
    try:
        sec_facts = scoring_facts_for_symbol(symbol) or sec_data.get_financials(symbol)
    except ValueError as e:
        err_msg = str(e)
        # Provide a more actionable message for foreign-listed tickers that
        # don't file with the SEC (e.g. BMO, TD, RY, SHOP.TO, etc.)
        if "not found in SEC database" in err_msg:
            err_msg = (
                f"{err_msg}. This app uses SEC EDGAR filings, which only covers "
                "US-listed companies that file 10-K/10-Q reports. Foreign-listed "
                "or OTC-only tickers (e.g. Canadian banks like BMO, TD, RY) are "
                "not supported. Try the US-listed ADR or a US-domiciled equivalent."
            )
        return {"error": err_msg}
    except Exception as e:
        print(f"[SEC EDGAR error] {symbol}: {e}")  # full detail server-side only
        return {"error": "Could not retrieve data for this ticker. Please try again shortly."}
    # Quality score (no price) — early calculation
    q = _component(timings, "quality", symbol, sec_facts, lambda: quality.score(sec_facts))
    # International prices require a licensed source with explicit quote
    # currency, unit, and adjustment metadata. Until that evidence is stored,
    # run fundamentals without price-based outputs.
    if sec_facts.get("source_market", "US") == "US":
        try:
            price = api_fetcher.get_price(symbol)
        except Exception as e:
            if _is_rate_limit_error(e):
                message = getattr(e, "user_message", str(e))
                return {"error": message}
            raise
    else:
        price = None
    # Earnings revision score
    earnings_revision_result = {"total_score": 0, "total_max": 100, "criteria": []}
    if price:
        try:
            earnings_revision_result = earnings_revision.get_revision_score(symbol)
        except Exception as e:
            print(f"Earnings revision calculation failed: {e}")
    hist = None
    spy_hist = None
    
    # 1B: Parallelize price history fetches with ThreadPoolExecutor
    if price:
        history_started = _time.perf_counter()
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Fetch stock history + use lazy-loaded SPY history
            hist_future = executor.submit(
                api_fetcher.get_price_history, symbol, 10
            )
            spy_hist_future = executor.submit(_get_spy_history_lazy)
            
            try:
                hist = hist_future.result(timeout=30)
            except Exception as e:
                if _is_rate_limit_error(e):
                    message = getattr(e, "user_message", str(e))
                    return {"error": message}
                print(f"Price history fetch failed for {symbol}: {e}")
            
            try:
                spy_hist = spy_hist_future.result(timeout=30)
            except Exception as e:
                print(f"SPY history fetch failed: {e}")
        timings["price_histories"] = round((_time.perf_counter() - history_started) * 1000, 2)
    # 1G: Calculate Graham score WITH price (if available), eliminating redundant call
    g = _component(timings, "graham", symbol, [price, sec_facts], lambda: graham.score(price, sec_facts) if price else graham.score(None, sec_facts))
    # Momentum score (needs price history)
    m_result = {"total_score": 0, "total_max": 100, "criteria": []}
    if price and hist is not None:
        try:
            sector_avg = screener.get_sector_avg_return_12m(
                sec_facts.get("sector"), exclude_symbol=symbol
            )
            m_result = momentum.score(hist, spy_hist, symbol,
                                    sector_avg_return_12m=sector_avg)
        except Exception as e:
            print(f"Momentum calculation failed: {e}")
    # Original composite (kept for backward-compat with screener)
    comp = _timed(timings, "composite", lambda: scorer.composite(g, q, m_result))
    # ── New quant modules ─────────────────────────────────────────────────
    piotroski_result = _component(timings, "piotroski", symbol, sec_facts, lambda: piotroski.score(sec_facts))
    altman_result = _component(timings, "altman", symbol, [price, sec_facts], lambda: altman.score(price, sec_facts))
    risk_result = {"risk_score": 50, "risk_score_max": 100, "risk_criteria": []}
    if hist is not None and not hist.empty:
        try:
            risk_result = risk_metrics.score(hist, spy_hist)
        except Exception as e:
            print(f"Risk metrics calculation failed: {e}")
    greenblatt_result = _component(timings, "greenblatt", symbol, [price, sec_facts], lambda: greenblatt.compute_single(price, sec_facts))
    buffett_result = _component(timings, "buffett", symbol, [price, sec_facts], lambda: buffett.score(price, sec_facts))
    # Profitability score (P1)
    profitability_result = None
    try:
        profitability_result = _component(
            timings, "profitability", symbol, sec_facts,
            lambda: profitability_model.ProfitabilityAnalyzer(symbol, sec_facts).get_profitability_score(),
        )
    except Exception as e:
        print(f"Profitability calculation failed: {e}")
    # FCF Quality score (P1)
    fcf_quality_result = None
    try:
        fcf_quality_result = _component(
            timings, "fcf_quality", symbol, sec_facts,
            lambda: fcf_quality_model.FCFQualityAnalyzer(symbol, sec_facts).get_fcf_quality_score(),
        )
    except Exception as e:
        print(f"FCF quality calculation failed: {e}")

    # Capital Allocation score (P2)
    capital_allocation_result = None
    try:
        capital_allocation_result = capital_allocation_model.CapitalAllocationAnalyzer(
            symbol, sec_facts, price
        ).get_capital_allocation_score()
    except Exception as e:
        print(f"Capital allocation calculation failed: {e}")
    # Growth Quality score (P2)
    growth_quality_result = None
    try:
        growth_quality_result = growth_quality_model.GrowthQualityAnalyzer(
            symbol, sec_facts
        ).get_growth_quality_score()
    except Exception as e:
        print(f"Growth quality calculation failed: {e}")
    transactions, sec_8k_filings, ownership_trends, patent_trends = [], [], [], []
    if not defer_secondary:
        provider_started = _time.perf_counter()
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="analysis-provider") as executor:
            provider_futures = {
                "transactions": executor.submit(provider_gateway.call, "finnhub", f"insiders:{symbol}", lambda: api_fetcher.get_insider_transactions(symbol), default=[]),
                "sec_8k": executor.submit(provider_gateway.call, "sec", f"8k:{symbol}", lambda: sec_data.get_recent_8k_filings(symbol), default=[]),
                "ownership": executor.submit(provider_gateway.call, "finnhub", f"ownership:{symbol}", lambda: api_fetcher.get_institutional_ownership_trends(symbol), default=[]),
                "patents": executor.submit(provider_gateway.call, "finnhub", f"patents:{symbol}", lambda: api_fetcher.get_patent_trends(symbol), default=[]),
            }
            transactions = provider_futures["transactions"].result()
            sec_8k_filings = provider_futures["sec_8k"].result()
            ownership_trends = provider_futures["ownership"].result()
            patent_trends = provider_futures["patents"].result()
        timings["secondary_providers"] = round((_time.perf_counter() - provider_started) * 1000, 2)

    insider_activity_result = None
    shares_out = None
    try:
        sh_recs = sec_facts.get("shares", [])
        if sh_recs:
            try:
                shares_out = float(sh_recs[0]["value"])
            except (KeyError, TypeError, ValueError):
                pass
        insider_activity_result = insider_activity_model.get_insider_score(
            symbol, transactions, shares_outstanding=shares_out
        )
    except Exception as e:
        print(f"Insider activity calculation failed: {e}")
    # Factor Momentum (P4)
    factor_momentum_result = None
    try:
        factor_momentum_result = (
            factor_momentum_model.FactorMomentumAnalyzer(
                symbol,
                hist,
                sec_facts
            ).get_factor_momentum_score()
        )
    except Exception as e:
        print(f"Factor momentum calculation failed: {e}")
    # Alternative Data (Phase E display-only framework)
    alternative_data_result = None
    try:
        alternative_data_result = alternative_data_model.get_alternative_data_score(
            symbol,
            sec_8k_filings=sec_8k_filings,
            insider_transactions=transactions,
            shares_outstanding=shares_out,
            ownership_trends=ownership_trends,
            patent_trends=patent_trends,
            market_provider_ready=api_fetcher.is_finnhub_configured(),
        )
    except Exception as e:
        print(f"Alternative data framework failed: {e}")
    # Enhanced orthogonal composite
    enhanced = scorer.enhanced_composite(
        g, q, m_result, piotroski_result, risk_result, altman_result, buffett_result,
        greenblatt_result=greenblatt_result, earnings_revision_result=earnings_revision_result,
        profitability_result=profitability_result, fcf_quality_result=fcf_quality_result,
        capital_allocation_result=capital_allocation_result,
        growth_quality_result=growth_quality_result,
        factor_momentum_result=factor_momentum_result,
    )
    

    # Regime overlay — uses SPY history already loaded above (portfolio risk layer)
    regime_result = None
    if spy_hist is not None and not spy_hist.empty:
        try:
            comomentum_result = _get_comomentum_result()
            regime_result = regime_model.score(spy_hist, comomentum_result=comomentum_result)
        except Exception as e:
            print(f"Regime calculation failed: {e}")
    regime_overlay = scorer.apply_regime_overlay(
        enhanced.get("composite_score", 0), regime_result
    )
    # SPY Benchmark + Bias (Outperform/Neutral/Underperform vs SPY) —
    # depends on price history + enhanced composite + Altman distress flag.
    spy_benchmark_result = None
    bias_result = None
    if hist is not None and not hist.empty and spy_hist is not None and not spy_hist.empty:
        try:
            spy_benchmark_result = _timed(
                timings, "spy_benchmark",
                lambda: spy_benchmark_model.compute_benchmark(hist, spy_hist),
            )
        except Exception as e:
            print(f"SPY benchmark calculation failed: {e}")
    if spy_benchmark_result and not spy_benchmark_result.get("error") \
            and spy_benchmark_result.get("probability_outperform") is not None:
        risk_score = risk_result.get("risk_score", 50) or 50
        risk_level = (
            bias_engine.RiskLevel.LOW if risk_score >= 65 else
            bias_engine.RiskLevel.MEDIUM if risk_score >= 35 else
            bias_engine.RiskLevel.HIGH
        )
        try:
            bias_result = bias_engine.classify(
                composite_score=enhanced.get("composite_score", 0) or 0,
                risk_level=risk_level,
                probability_outperform=spy_benchmark_result["probability_outperform"],
                distress_flag=bool(enhanced.get("altman_cap_applied")),
            )
        except Exception as e:
            print(f"Bias classification failed: {e}")
    # Market cap for persistence/screener ordering.
    # Prefer graham.score()'s value (price × shares, $M); if unavailable
    # (no live price), fall back to live price (Tiingo/Finnhub via
    # api_fetcher.get_price) × shares outstanding from sec_facts.
    market_cap = g.get("market_cap")
    if market_cap is None and price:
        try:
            shares_recs = sec_facts.get("shares", [])
            shares_val = float(shares_recs[0]["value"]) if shares_recs else None
            if shares_val:
                market_cap = price * shares_val / 1e6
        except (KeyError, TypeError, ValueError, IndexError):
            pass
    result = {
        "analysis_version": ANALYSIS_VERSION,
        "model_versions": _MODEL_VERSIONS,
        "generated_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "symbol":    symbol,
        "market_code": sec_facts.get("source_market", "US"),
        "name":      security.sanitize_string(sec_facts["name"], max_length=200),
        "sector":    sec_facts["sector"],
        "price":     price,
        "market_cap": market_cap,
        "graham":    g,
        "quality":   q,
        "momentum":  m_result,
        "composite": comp,
        # ── New ──────────────────────────────────────────
        "piotroski":   piotroski_result,
        "altman":      altman_result,
        "risk":        risk_result,
        "greenblatt":  greenblatt_result,
        "buffett":     buffett_result,
        "earnings_revision": earnings_revision_result,
        "profitability": profitability_result,
        "fcf_quality": fcf_quality_result,
        "capital_allocation": capital_allocation_result,
        "growth_quality": growth_quality_result,
        "insider_activity":   insider_activity_result,
        "factor_momentum": factor_momentum_result,
        "alternative_data": alternative_data_result,
        "secondary_status": "pending" if defer_secondary else "complete",
        "market_fear":       _get_market_fear_result(),
        "regime":             regime_result,
        "regime_overlay":     regime_overlay,
        "enhanced":    enhanced,
        "spy_benchmark":      spy_benchmark_result,
        "bias":               bias_result,
        "performance": {
            "models_ms": timings,
            "pipeline_ms": round((_time.perf_counter() - analysis_started) * 1000, 2),
        },
        # ─────────────────────────────────────────────────
        "price_history": hist.to_dict() if hist is not None else None,
        "spy_history": spy_hist.to_dict() if spy_hist is not None else None,
    }
    _set_cache_metadata(result, False, "fresh")
    factor_engine.persist_factor_scores(symbol, {
        "graham": g, "quality": q, "momentum": m_result,
        "piotroski": piotroski_result, "risk": risk_result, "buffett": buffett_result,
        "earnings_revision": earnings_revision_result, "profitability": profitability_result,
        "fcf_quality": fcf_quality_result, "capital_allocation": capital_allocation_result,
        "growth_quality": growth_quality_result,
    })
    composite_source = enhanced if enhanced.get("composite_score") is not None else comp
    db.record_composite_score_snapshot(
        symbol,
        composite_source.get("composite_score", 0),
        composite_source.get("verdict"),
    )
    db.upsert_analysis(symbol, result)
    if defer_secondary:
        analysis_jobs.enqueue({"type": "secondary-analysis", "symbol": symbol, "shares_out": shares_out})
    try:
        save_standard_snapshot(result, analysis_type=AnalysisType.STANDARD)
    except Exception as e:
        print(f"Analysis snapshot save failed for {symbol}: {type(e).__name__}: {e}")
    
    # 1A: Update in-memory cache
    with _analysis_cache_lock:
        _analysis_cache[symbol] = result

    performance_metrics.record_analysis(result["performance"]["pipeline_ms"], False)
    return result


def _complete_secondary_analysis(symbol: str, shares_out: float | None) -> None:
    """Fetch display-only enrichment after the primary analysis is visible."""
    try:
        transactions = provider_gateway.call("finnhub", f"insiders:{symbol}", lambda: api_fetcher.get_insider_transactions(symbol), default=[])
        sec_8k = provider_gateway.call("sec", f"8k:{symbol}", lambda: sec_data.get_recent_8k_filings(symbol), default=[])
        ownership = provider_gateway.call("finnhub", f"ownership:{symbol}", lambda: api_fetcher.get_institutional_ownership_trends(symbol), default=[])
        patents = provider_gateway.call("finnhub", f"patents:{symbol}", lambda: api_fetcher.get_patent_trends(symbol), default=[])
        current = db.get_analysis(symbol) or {}
        current["insider_activity"] = insider_activity_model.get_insider_score(symbol, transactions, shares_outstanding=shares_out)
        current["alternative_data"] = alternative_data_model.get_alternative_data_score(
            symbol,
            sec_8k_filings=sec_8k,
            insider_transactions=transactions,
            shares_outstanding=shares_out,
            ownership_trends=ownership,
            patent_trends=patents,
            market_provider_ready=api_fetcher.is_finnhub_configured(),
        )
        current["secondary_status"] = "complete"
    except Exception as exc:
        print(f"Secondary analysis failed for {symbol}: {exc}")
        current = db.get_analysis(symbol) or {}
        current["secondary_status"] = "failed"
    db.upsert_analysis(symbol, current)
    with _analysis_cache_lock:
        _analysis_cache[symbol] = current


def analyze_stock(symbol: str, *, force_refresh: bool = False, defer_secondary: bool = False) -> dict:
    normalized = (symbol or "").strip().upper()
    mode = "refresh" if force_refresh else "primary" if defer_secondary else "request"
    return singleflight.run(
        f"analysis:{normalized}:{ANALYSIS_VERSION}:{mode}",
        lambda: _analyze_stock(normalized, force_refresh=force_refresh, defer_secondary=defer_secondary),
        timeout=120,
        result_ttl=10,
    )


def analyze_stock_primary(symbol: str) -> dict:
    """Fast web entrypoint; display-only enrichment completes in background."""
    return analyze_stock(symbol, defer_secondary=True)
