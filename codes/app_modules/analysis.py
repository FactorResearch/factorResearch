"""Stock analysis pipeline and analysis-level caches."""

import os
import threading
import time as _time
from concurrent.futures import ThreadPoolExecutor

from codes import security
from codes.data import api_fetcher, sec_data, db
from codes.data.api_fetcher import RateLimitError
from codes.engine import factor_engine, scorer, screener
from codes.models import (
    graham, quality, momentum, piotroski, altman, risk_metrics, greenblatt,
    buffett, earnings_revision, profitability as profitability_model,
    fcf_quality as fcf_quality_model, capital_allocation as capital_allocation_model,
    growth_quality as growth_quality_model, regime as regime_model,
    insider_activity as insider_activity_model, factor_momentum as factor_momentum_model,
    alternative_data as alternative_data_model, options_signal_engine as options_signal_model,
    spy_benchmark_model, bias_engine, comomentum as comomentum_model,
)
from codes.models.analysis_snapshot import AnalysisType
from codes.services.analysis_snapshot_service import save_standard_snapshot

from .config import validate_ticker

# ── Performance Optimization: Module-level caches ─────────────────────────────
_spy_history = None
_spy_history_lock = threading.Lock()
_analysis_cache = {}
_analysis_cache_lock = threading.Lock()
_comomentum_cache = {"ts": 0.0, "result": None}
_comomentum_lock = threading.Lock()
_COMOMENTUM_TTL = 3600  # seconds
_COMOMENTUM_TOP_N = 20

def _get_spy_history_lazy():
    """Fetch SPY history once at startup, cache it module-level. Subsequent calls are instant."""
    global _spy_history
    if _spy_history is not None:
        return _spy_history
    
    with _spy_history_lock:
        if _spy_history is not None:  # Double-check after acquiring lock
            return _spy_history
        try:
            _spy_history = api_fetcher.get_price_history("SPY", years=10)
        except Exception as e:
            print(f"Failed to fetch SPY history: {e}")
            _spy_history = None  # Cache failure so we don't retry every time
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
        if _comomentum_cache["result"] is not None and now - _comomentum_cache["ts"] < _COMOMENTUM_TTL:
            return _comomentum_cache["result"]

    try:
        results = screener.get_screener_results()
        candidates = [
            r["symbol"] for r in results
            if r.get("analyzed") and r.get("return_12m") is not None
        ]
        candidates.sort(
            key=lambda s: next(r["return_12m"] for r in results if r["symbol"] == s),
            reverse=True,
        )
        top_symbols = candidates[:_COMOMENTUM_TOP_N]
        if len(top_symbols) < 2:
            return None

        price_histories = {}
        for sym in top_symbols:
            try:
                h = api_fetcher.get_price_history(sym, years=3)
                if h is not None and not h.empty:
                    price_histories[sym] = h
            except Exception as e:
                print(f"Comomentum: history fetch failed for {sym}: {e}")

        result = comomentum_model.calc_comomentum(top_symbols, price_histories)
    except Exception as e:
        print(f"Comomentum calculation failed: {e}")
        result = None

    with _comomentum_lock:
        _comomentum_cache = {"ts": now, "result": result}
    return result
def is_production() -> bool:
    
    return os.environ.get("FLASK_ENV", "").lower() == "production"
def analyze_stock(symbol: str) -> dict:
    """Full pipeline: SEC → Graham + Quality + (Price→Momentum) → Composite.
    
    Optimizations:
    - 1A: In-memory cache for repeat lookups
    - 1G: Eliminate redundant graham.score(None, ...) call
    - 1B: Parallelize network fetches with ThreadPoolExecutor
    - 1C: Lazy-load SPY history once, reuse across all stocks
    """
    global _analysis_cache, _analysis_cache_lock

    symbol = validate_ticker(symbol)
    if not symbol:
        return {"error": "Invalid ticker format."}
    # 1A: Check in-memory cache first (zero disk I/O for repeat lookups)
    with _analysis_cache_lock:
        if symbol in _analysis_cache:
            cached_memory = _analysis_cache[symbol]
            try:
                save_standard_snapshot(cached_memory, analysis_type=AnalysisType.STANDARD)
            except Exception as e:
                print(f"Analysis snapshot save failed for {symbol}: {type(e).__name__}: {e}")
            return cached_memory
    # Then try disk cache
    cached = db.get_analysis(symbol)

    if cached:
        try:
            save_standard_snapshot(cached, analysis_type=AnalysisType.STANDARD)
        except Exception as e:
            print(f"Analysis snapshot save failed for {symbol}: {type(e).__name__}: {e}")
        with _analysis_cache_lock:
            _analysis_cache[symbol] = cached
        return cached
    # Fetch SEC fundamentals — lazy: returns cache instantly when not stale
    try:
        sec_facts = sec_data.get_financials(symbol)
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
    q = quality.score(sec_facts)
    # Now try to get price
    try:
        price = api_fetcher.get_price(symbol)
    except Exception as e:
        if _is_rate_limit_error(e):
            message = getattr(e, "user_message", str(e))
            return {"error": message}
        raise
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
    # 1G: Calculate Graham score WITH price (if available), eliminating redundant call
    g = graham.score(price, sec_facts) if price else graham.score(None, sec_facts)
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
    comp = scorer.composite(g, q, m_result)
    # ── New quant modules ─────────────────────────────────────────────────
    piotroski_result = piotroski.score(sec_facts)
    altman_result = altman.score(price, sec_facts)
    risk_result = {"risk_score": 50, "risk_score_max": 100, "risk_criteria": []}
    if hist is not None and not hist.empty:
        try:
            risk_result = risk_metrics.score(hist, spy_hist)
        except Exception as e:
            print(f"Risk metrics calculation failed: {e}")
    greenblatt_result = greenblatt.compute_single(price, sec_facts)
    buffett_result = buffett.score(price, sec_facts)
    # Profitability score (P1)
    profitability_result = None
    try:
        profitability_result = profitability_model.ProfitabilityAnalyzer(symbol, sec_facts).get_profitability_score()
    except Exception as e:
        print(f"Profitability calculation failed: {e}")
    # FCF Quality score (P1)
    fcf_quality_result = None
    try:
        fcf_quality_result = fcf_quality_model.FCFQualityAnalyzer(symbol, sec_facts).get_fcf_quality_score()
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
    # Insider Activity (P4)
    insider_activity_result = None
    transactions = []
    shares_out = None
    try:
        transactions = api_fetcher.get_insider_transactions(symbol)
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
        sec_8k_filings = []
        ownership_trends = []
        patent_trends = []
        try:
            sec_8k_filings = sec_data.get_recent_8k_filings(symbol)
        except Exception as e:
            print(f"SEC 8-K fetch failed for {symbol}: {e}")
        try:
            ownership_trends = api_fetcher.get_institutional_ownership_trends(symbol)
        except Exception as e:
            print(f"Institutional ownership fetch failed for {symbol}: {e}")
        try:
            patent_trends = api_fetcher.get_patent_trends(symbol)
        except Exception as e:
            print(f"Patent activity fetch failed for {symbol}: {e}")
        alternative_data_result = alternative_data_model.get_alternative_data_score(
            symbol,
            sec_8k_filings=sec_8k_filings,
            insider_transactions=transactions,
            shares_outstanding=shares_out,
            ownership_trends=ownership_trends,
            patent_trends=patent_trends,
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
    # Options Signal (P4) — depends on regime + risk + price history
    options_signal_result = None
    try:
        options_signal_result = options_signal_model.get_options_signal(
            symbol, price_hist=hist, regime_result=regime_result,
            risk_result=risk_result, current_price=price,
        )
    except Exception as e:
        print(f"Options signal calculation failed: {e}")
    # SPY Benchmark + Bias (Outperform/Neutral/Underperform vs SPY) —
    # depends on price history + enhanced composite + Altman distress flag.
    spy_benchmark_result = None
    bias_result = None
    if hist is not None and not hist.empty and spy_hist is not None and not spy_hist.empty:
        try:
            spy_benchmark_result = spy_benchmark_model.compute_benchmark(hist, spy_hist)
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
        "symbol":    symbol,
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
        "regime":             regime_result,
        "regime_overlay":     regime_overlay,
        "enhanced":    enhanced,
        "options_signal":     options_signal_result,
        "spy_benchmark":      spy_benchmark_result,
        "bias":               bias_result,
        # ─────────────────────────────────────────────────
        "price_history": hist.to_dict() if hist is not None else None,
        "spy_history": spy_hist.to_dict() if spy_hist is not None else None,
    }
    factor_engine.persist_factor_scores(symbol, {
        "graham": g, "quality": q, "momentum": m_result,
        "piotroski": piotroski_result, "risk": risk_result, "buffett": buffett_result,
        "earnings_revision": earnings_revision_result, "profitability": profitability_result,
        "fcf_quality": fcf_quality_result, "capital_allocation": capital_allocation_result,
        "growth_quality": growth_quality_result,
    })
    db.upsert_analysis(symbol, result)
    try:
        save_standard_snapshot(result, analysis_type=AnalysisType.STANDARD)
    except Exception as e:
        print(f"Analysis snapshot save failed for {symbol}: {type(e).__name__}: {e}")
    
    # 1A: Update in-memory cache
    with _analysis_cache_lock:
        _analysis_cache[symbol] = result
    
    return result
