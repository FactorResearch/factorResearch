"""
Alternative Data Model - Phase E.

Phase E defines provider-ready alternative data signals while keeping the app
deterministic, auditable, and display-only. SEC 8-K sentiment can be computed
from caller-supplied filing text with a fixed lexicon and no external AI
dependency. Provider-dependent signals remain neutral until durable data
sources are wired in.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Iterable

from codes.core import model_utils as mu

try:
    from . import insider_activity
except ImportError:  # tests import this module directly from codes/models
    import insider_activity


NEUTRAL_SCORE = 50.0

STATUS_AVAILABLE = "AVAILABLE"
STATUS_NO_DATA = "NO_DATA"
STATUS_PLANNED = "PLANNED"
STATUS_WAITING_FOR_SOURCE = "WAITING_FOR_SOURCE"
STATUS_RESEARCH = "RESEARCH"
STATUS_CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"

_WORD_RE = re.compile(r"[a-z][a-z\-']+")

_POSITIVE_8K_TERMS = {
    "accretive",
    "award",
    "awarded",
    "beneficial",
    "confidence",
    "exceed",
    "exceeded",
    "expansion",
    "favorable",
    "growth",
    "improved",
    "improvement",
    "profitable",
    "record",
    "resolved",
    "strong",
    "strengthened",
    "successful",
    "upgrade",
}

_NEGATIVE_8K_TERMS = {
    "adverse",
    "breach",
    "charge",
    "default",
    "delay",
    "delayed",
    "decline",
    "deterioration",
    "downgrade",
    "impairment",
    "investigation",
    "lawsuit",
    "loss",
    "material weakness",
    "restructuring",
    "restatement",
    "terminated",
    "weak",
    "weakness",
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return mu.clamp(value, low, high)


def _signal(score: float) -> str:
    if score >= 60:
        return "BULLISH"
    if score <= 40:
        return "BEARISH"
    return "NEUTRAL"


def _base_signal(
    name: str,
    label: str,
    description: str,
    *,
    status: str,
    source: str | None,
    phase: str = "Phase E",
    score: float = NEUTRAL_SCORE,
    available: bool = False,
    value: Any = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "score": round(_clamp(score), 2),
        "signal": _signal(score),
        "status": status,
        "available": available,
        "value": value,
        "description": description,
        "source": source,
        "phase": phase,
        "details": details or {},
    }


def _score_from_delta(delta_pct: float, *, scale: float = 2.0) -> float:
    """Map a signed percent change to 0-100, centered at neutral."""
    return _clamp(50.0 + (delta_pct * scale))


def _latest_prior_values(records: Iterable[Any] | None) -> tuple[float | None, float | None]:
    """
    Pull latest and prior numeric values from simple time-series records.

    Accepts numbers directly or dicts with value-like keys. Dicts are sorted by
    common date keys when present.
    """
    if not records:
        return None, None

    rows = []
    for idx, record in enumerate(records):
        if isinstance(record, dict):
            raw_value = (
                record.get("value")
                if record.get("value") is not None
                else record.get("count")
                if record.get("count") is not None
                else record.get("visits")
                if record.get("visits") is not None
                else record.get("patents")
            )
            date_key = (
                record.get("date")
                or record.get("as_of")
                or record.get("period")
                or record.get("month")
                or idx
            )
        else:
            raw_value = record
            date_key = idx
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        rows.append((str(date_key), value))

    if len(rows) < 2:
        return None, rows[-1][1] if rows else None

    rows.sort(key=lambda item: item[0])
    return rows[-1][1], rows[0][1]


def _trend_signal_value(records: Iterable[Any] | None) -> dict[str, Any]:
    latest, prior = _latest_prior_values(records)
    if latest is None or prior is None or prior <= 0:
        return {
            "score": NEUTRAL_SCORE,
            "status": STATUS_NO_DATA,
            "available": False,
            "value": None,
            "details": {"method": "trend_delta_v1"},
        }
    delta_pct = ((latest - prior) / prior) * 100.0
    score = round(_score_from_delta(delta_pct), 2)
    return {
        "score": score,
        "status": STATUS_AVAILABLE,
        "available": True,
        "value": {"latest": latest, "prior": prior, "delta_pct": round(delta_pct, 2)},
        "details": {"method": "trend_delta_v1"},
    }


def _filing_text(filing: Any) -> str:
    if isinstance(filing, str):
        return filing
    if not isinstance(filing, dict):
        return ""
    parts = [
        filing.get("title"),
        filing.get("summary"),
        filing.get("text"),
        filing.get("body"),
    ]
    items = filing.get("items")
    if isinstance(items, dict):
        parts.extend(str(v) for v in items.values())
    elif isinstance(items, list):
        parts.extend(str(v) for v in items)
    return " ".join(str(p) for p in parts if p)


def analyze_sec_8k_sentiment(filings: Iterable[Any] | None) -> dict[str, Any]:
    """
    Score SEC 8-K text with a fixed, auditable term dictionary.

    This intentionally avoids external AI calls. Scores are neutral when no
    8-K text is supplied; callers can pass cached SEC filing text later without
    changing the public Phase E schema.
    """
    texts = [_filing_text(f) for f in (filings or [])]
    text = "\n".join(t for t in texts if t).lower()
    if not text.strip():
        return {
            "score": NEUTRAL_SCORE,
            "signal": "NEUTRAL",
            "status": STATUS_NO_DATA,
            "available": False,
            "value": None,
            "details": {
                "filings_analyzed": 0,
                "positive_hits": 0,
                "negative_hits": 0,
                "method": "fixed_lexicon_v1",
            },
        }

    tokens = _WORD_RE.findall(text)
    token_text = " ".join(tokens)
    positive_hits = sum(
        tokens.count(term) for term in _POSITIVE_8K_TERMS if " " not in term
    )
    negative_hits = sum(
        tokens.count(term) for term in _NEGATIVE_8K_TERMS if " " not in term
    )
    positive_hits += sum(token_text.count(term) for term in _POSITIVE_8K_TERMS if " " in term)
    negative_hits += sum(token_text.count(term) for term in _NEGATIVE_8K_TERMS if " " in term)

    total_hits = positive_hits + negative_hits
    if total_hits == 0:
        score = NEUTRAL_SCORE
    else:
        score = 50.0 + ((positive_hits - negative_hits) / total_hits) * 35.0

    score = round(_clamp(score), 2)
    return {
        "score": score,
        "signal": _signal(score),
        "status": STATUS_AVAILABLE,
        "available": True,
        "value": {
            "positive_hits": positive_hits,
            "negative_hits": negative_hits,
        },
        "details": {
            "filings_analyzed": len([t for t in texts if t.strip()]),
            "positive_hits": positive_hits,
            "negative_hits": negative_hits,
            "method": "fixed_lexicon_v1",
            "positive_terms": sorted(_POSITIVE_8K_TERMS),
            "negative_terms": sorted(_NEGATIVE_8K_TERMS),
        },
    }


def get_sec_8k_sentiment_signal(
    ticker: str,
    filings: Iterable[Any] | None = None,
) -> dict[str, Any]:
    result = analyze_sec_8k_sentiment(filings)
    return _base_signal(
        "sec_8k_sentiment",
        "SEC 8-K Sentiment",
        "Deterministic, auditable 8-K sentiment analysis with no external AI dependency.",
        status=result["status"],
        source="SEC EDGAR 8-K filings",
        score=result["score"],
        available=result["available"],
        value=result["value"],
        details=result["details"],
    )


def get_hiring_velocity_signal(ticker: str) -> dict[str, Any]:
    return get_hiring_velocity_signal_from_records(ticker, None)


def get_hiring_velocity_signal_from_records(
    ticker: str,
    job_posting_trends: Iterable[Any] | None,
) -> dict[str, Any]:
    trend = _trend_signal_value(job_posting_trends)
    status = trend["status"] if trend["available"] else STATUS_PLANNED
    return _base_signal(
        "hiring_velocity",
        "Hiring Velocity",
        "Hiring velocity via job posting trends.",
        status=status,
        source=None,
        score=trend["score"],
        available=trend["available"],
        value=trend["value"],
        details=trend["details"],
    )


def get_web_traffic_signal(ticker: str) -> dict[str, Any]:
    return get_web_traffic_signal_from_records(ticker, None)


def get_web_traffic_signal_from_records(
    ticker: str,
    web_traffic_trends: Iterable[Any] | None,
) -> dict[str, Any]:
    trend = _trend_signal_value(web_traffic_trends)
    status = trend["status"] if trend["available"] else STATUS_WAITING_FOR_SOURCE
    return _base_signal(
        "web_traffic",
        "Web Traffic Analytics",
        "Web traffic analytics once a reliable long-term data source is available.",
        status=status,
        source=None,
        score=trend["score"],
        available=trend["available"],
        value=trend["value"],
        details=trend["details"],
    )


def get_insider_trends_signal(
    ticker: str,
    transactions: list[dict] | None = None,
    shares_outstanding: float | None = None,
    reference_date: datetime | None = None,
    provider_ready: bool | None = None,
) -> dict[str, Any]:
    if transactions:
        score = insider_activity.get_insider_score(
            ticker,
            transactions,
            shares_outstanding=shares_outstanding,
            reference_date=reference_date,
        )
        return _base_signal(
            "insider_trends",
            "Insider Buying/Selling Trends",
            "Insider buying and selling trends.",
            status=STATUS_AVAILABLE,
            source="SEC Form 4 / provider transaction feeds",
            score=score["insider_confidence_score"],
            available=True,
            value={
                "net_insider_buying": score["net_insider_buying"],
                "n_buy_transactions": score["n_buy_transactions"],
                "n_sell_transactions": score["n_sell_transactions"],
                "cluster_detected": score["cluster_detected"],
            },
            details={
                "method": "insider_activity_v1",
                "cluster_buying_score": score["cluster_buying_score"],
                "insider_type_quality": score["insider_type_quality"],
                "n_distinct_buyers": score["n_distinct_buyers"],
                "low_coverage": score["low_coverage"],
            },
        )

    status = STATUS_CONFIGURATION_REQUIRED if provider_ready is False else STATUS_PLANNED
    return _base_signal(
        "insider_trends",
        "Insider Buying/Selling Trends",
        "Insider buying and selling trends.",
        status=status,
        source="SEC Form 4 / provider transaction feeds",
        details={"provider_configuration_required": provider_ready is False},
    )


def get_institutional_ownership_signal(
    ticker: str,
    ownership_trends: Iterable[Any] | None = None,
    provider_ready: bool | None = None,
) -> dict[str, Any]:
    trend = _trend_signal_value(ownership_trends)
    status = (
        trend["status"] if trend["available"] else
        STATUS_CONFIGURATION_REQUIRED if provider_ready is False else STATUS_PLANNED
    )
    return _base_signal(
        "institutional_ownership",
        "Institutional Ownership Changes",
        "Institutional ownership changes.",
        status=status,
        source="SEC 13F filings / provider ownership feeds",
        score=trend["score"],
        available=trend["available"],
        value=trend["value"],
        details={
            **trend["details"],
            "provider_configuration_required": provider_ready is False,
        },
    )


def get_patent_activity_signal(
    ticker: str,
    patent_trends: Iterable[Any] | None = None,
    provider_ready: bool | None = None,
) -> dict[str, Any]:
    trend = _trend_signal_value(patent_trends)
    status = (
        trend["status"] if trend["available"] else
        STATUS_CONFIGURATION_REQUIRED if provider_ready is False else STATUS_PLANNED
    )
    return _base_signal(
        "patent_activity",
        "Patent/IP Activity",
        "Patent and intellectual property activity.",
        status=status,
        source="USPTO / patent data providers",
        score=trend["score"],
        available=trend["available"],
        value=trend["value"],
        details={
            **trend["details"],
            "provider_configuration_required": provider_ready is False,
        },
    )


def get_supply_chain_signal(
    ticker: str,
    relationship_trends: Iterable[Any] | None = None,
) -> dict[str, Any]:
    trend = _trend_signal_value(relationship_trends)
    status = trend["status"] if trend["available"] else STATUS_RESEARCH
    return _base_signal(
        "supply_chain_relationships",
        "Supply Chain Relationships",
        "Supply chain relationship analysis.",
        status=status,
        source=None,
        score=trend["score"],
        available=trend["available"],
        value=trend["value"],
        details=trend["details"],
    )


def get_alternative_data_score(
    ticker: str,
    *,
    sec_8k_filings: Iterable[Any] | None = None,
    insider_transactions: list[dict] | None = None,
    shares_outstanding: float | None = None,
    job_posting_trends: Iterable[Any] | None = None,
    web_traffic_trends: Iterable[Any] | None = None,
    ownership_trends: Iterable[Any] | None = None,
    patent_trends: Iterable[Any] | None = None,
    supply_chain_trends: Iterable[Any] | None = None,
    reference_date: datetime | None = None,
    market_provider_ready: bool | None = None,
) -> dict[str, Any]:
    """
    Return a JSON-compatible Phase E alternative-data result.

    The output includes total_score / total_max for future scorer compatibility,
    but app/scorer wiring deliberately treats it as display-only until durable
    provider-backed data exists.
    """
    symbol = ticker.upper().strip()
    signals = [
        get_sec_8k_sentiment_signal(symbol, sec_8k_filings),
        get_hiring_velocity_signal_from_records(symbol, job_posting_trends),
        get_web_traffic_signal_from_records(symbol, web_traffic_trends),
        get_insider_trends_signal(
            symbol,
            insider_transactions,
            shares_outstanding,
            reference_date,
            market_provider_ready,
        ),
        get_institutional_ownership_signal(
            symbol, ownership_trends, market_provider_ready
        ),
        get_patent_activity_signal(symbol, patent_trends, market_provider_ready),
        get_supply_chain_signal(symbol, supply_chain_trends),
    ]
    available_scores = [s["score"] for s in signals if s["available"]]
    score = (
        round(sum(available_scores) / len(available_scores), 2)
        if available_scores
        else NEUTRAL_SCORE
    )

    return {
        "ticker": symbol,
        "alternative_data_score": score,
        "signal": _signal(score),
        "status": STATUS_AVAILABLE if available_scores else STATUS_NO_DATA,
        "available": bool(available_scores),
        "low_coverage": len(available_scores) < 3,
        "provider": None,
        "phase": "Phase E",
        "signals": signals,
        "total_score": score,
        "total_max": 100.0,
    }
