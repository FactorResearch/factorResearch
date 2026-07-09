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
from typing import Any, Iterable


NEUTRAL_SCORE = 50.0

STATUS_AVAILABLE = "AVAILABLE"
STATUS_NO_DATA = "NO_DATA"
STATUS_PLANNED = "PLANNED"
STATUS_WAITING_FOR_SOURCE = "WAITING_FOR_SOURCE"
STATUS_RESEARCH = "RESEARCH"

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
    return max(low, min(high, float(value)))


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
    return _base_signal(
        "hiring_velocity",
        "Hiring Velocity",
        "Hiring velocity via job posting trends.",
        status=STATUS_PLANNED,
        source=None,
    )


def get_web_traffic_signal(ticker: str) -> dict[str, Any]:
    return _base_signal(
        "web_traffic",
        "Web Traffic Analytics",
        "Web traffic analytics once a reliable long-term data source is available.",
        status=STATUS_WAITING_FOR_SOURCE,
        source=None,
    )


def get_insider_trends_signal(ticker: str) -> dict[str, Any]:
    return _base_signal(
        "insider_trends",
        "Insider Buying/Selling Trends",
        "Insider buying and selling trends.",
        status=STATUS_PLANNED,
        source="SEC Form 4 / provider transaction feeds",
    )


def get_institutional_ownership_signal(ticker: str) -> dict[str, Any]:
    return _base_signal(
        "institutional_ownership",
        "Institutional Ownership Changes",
        "Institutional ownership changes.",
        status=STATUS_PLANNED,
        source="SEC 13F filings / provider ownership feeds",
    )


def get_patent_activity_signal(ticker: str) -> dict[str, Any]:
    return _base_signal(
        "patent_activity",
        "Patent/IP Activity",
        "Patent and intellectual property activity.",
        status=STATUS_PLANNED,
        source="USPTO / patent data providers",
    )


def get_supply_chain_signal(ticker: str) -> dict[str, Any]:
    return _base_signal(
        "supply_chain_relationships",
        "Supply Chain Relationships",
        "Supply chain relationship analysis.",
        status=STATUS_RESEARCH,
        source=None,
    )


def get_alternative_data_score(
    ticker: str,
    *,
    sec_8k_filings: Iterable[Any] | None = None,
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
        get_hiring_velocity_signal(symbol),
        get_web_traffic_signal(symbol),
        get_insider_trends_signal(symbol),
        get_institutional_ownership_signal(symbol),
        get_patent_activity_signal(symbol),
        get_supply_chain_signal(symbol),
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
