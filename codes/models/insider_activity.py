"""
Insider Activity Model — behavioral conviction signal.

Measures insider trading behavior to detect management conviction
and short-term alpha signals.

Metrics & weights:
  Net Insider Buying       40%  — net buy/sell volume normalized to shares outstanding
  Cluster Buying Score     40%  — multiple insiders buying in a short window
  Insider Type Quality     20%  — CEO/CFO/Director buys weighted higher

Signal mapping:
  >= 70  → BULLISH
  40–69  → NEUTRAL
  < 40   → BEARISH

Input schema (list of transaction dicts):
  [
    {
      "date":        str,          # "YYYY-MM-DD"
      "insider_id":  str,          # unique identifier per insider
      "role":        str,          # "CEO", "CFO", "Director", "VP", "Other", etc.
      "transaction": str,          # "buy" | "sell" | "option_exercise"
      "shares":      float,        # number of shares
      "is_open_market": bool,      # True = open-market transaction
    },
    ...
  ]

Assumptions:
  - Option exercises are excluded unless is_open_market=True.
  - shares_outstanding is used for net buying normalization; if absent or zero,
    normalization falls back to total traded volume in the window.
  - Lookback for cluster detection is 30 trading days (~42 calendar days).
  - Recency decay for cluster scoring: linear from 1.0 (today) to 0.0 (42d ago).
  - "High-quality" insider roles: CEO, CFO, COO, President, Chairman, Director.
  - Cluster threshold: >=2 distinct insiders, >=3 buy transactions, no single
    insider exceeds 80% of cluster buy volume.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

CLUSTER_WINDOW_DAYS   = 42          # ~30 trading days in calendar days
CLUSTER_MIN_INSIDERS  = 2
CLUSTER_MIN_TRADES    = 3
CLUSTER_MAX_CONC      = 0.80        # one insider cannot exceed 80% of cluster vol

HIGH_QUALITY_ROLES = {
    "ceo", "cfo", "coo", "president", "chairman",
    "director", "executive chairman", "chief executive",
    "chief financial", "chief operating",
}

SIGNAL_THRESHOLDS = [
    (70, "BULLISH"),
    (40, "NEUTRAL"),
    (0,  "BEARISH"),
]

# Neutral defaults returned when data is insufficient
_NEUTRAL = {
    "net_insider_buying":      0.0,
    "cluster_buying_score":    0.0,
    "insider_type_quality":    50.0,
    "insider_confidence_score": 50.0,
    "signal":                  "NEUTRAL",
    "n_buy_transactions":      0,
    "n_sell_transactions":     0,
    "n_distinct_buyers":       0,
    "cluster_detected":        False,
    "low_coverage":            True,
    "total_score":             50.0,
    "total_max":               100.0,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe(val: Any) -> float | None:
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _parse_date(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _is_high_quality(role: str) -> bool:
    if not role:
        return False
    r = role.strip().lower()
    return any(hq in r for hq in HIGH_QUALITY_ROLES)


def _signal(score: float) -> str:
    for threshold, sig in SIGNAL_THRESHOLDS:
        if score >= threshold:
            return sig
    return "BEARISH"


# ── Filter helpers ────────────────────────────────────────────────────────────

def _filter_transactions(
    transactions: list[dict],
    lookback_days: int = 365,
    reference_date: datetime | None = None,
) -> list[dict]:
    """
    Return only open-market buy/sell transactions within the lookback window.
    Option exercises are excluded unless is_open_market=True.
    """
    ref = reference_date or datetime.utcnow()
    cutoff = ref - timedelta(days=lookback_days)
    out = []
    for t in transactions:
        d = _parse_date(t.get("date"))
        if d is None or d < cutoff or d > ref:
            continue
        tx = str(t.get("transaction", "")).strip().lower()
        if tx not in ("buy", "sell"):
            continue
        # Exclude option exercises unless flagged as open-market
        if tx == "buy" and not t.get("is_open_market", True):
            continue
        shares = _safe(t.get("shares"))
        if shares is None or shares <= 0:
            continue
        out.append({
            "date":       d,
            "insider_id": str(t.get("insider_id", "")),
            "role":       str(t.get("role", "")),
            "tx":         tx,
            "shares":     shares,
        })
    return out


# ── Metric 1: Net Insider Buying ──────────────────────────────────────────────

def calc_net_insider_buying(
    transactions: list[dict],
    shares_outstanding: float | None = None,
    reference_date: datetime | None = None,
) -> float:
    """
    Net insider buying as a fraction of shares outstanding (or total volume).
    Returns a signed float clipped to [-100, +100].
    """
    filtered = _filter_transactions(transactions, lookback_days=365,
                                    reference_date=reference_date)
    buy_vol  = sum(t["shares"] for t in filtered if t["tx"] == "buy")
    sell_vol = sum(t["shares"] for t in filtered if t["tx"] == "sell")
    net      = buy_vol - sell_vol

    denom = _safe(shares_outstanding) if shares_outstanding else None
    if not denom or denom <= 0:
        total_vol = buy_vol + sell_vol
        denom = total_vol if total_vol > 0 else 1.0

    pct = (net / denom) * 100.0
    return _clamp(pct, -100.0, 100.0)


# ── Metric 2: Cluster Buying Detection ───────────────────────────────────────

def calc_cluster_buying_score(
    transactions: list[dict],
    reference_date: datetime | None = None,
) -> tuple[float, bool]:
    """
    Returns (score 0-100, cluster_detected bool).

    Cluster rules (within CLUSTER_WINDOW_DAYS calendar days):
      - >= CLUSTER_MIN_INSIDERS distinct insiders bought
      - >= CLUSTER_MIN_TRADES total buy transactions
      - No single insider accounts for >= CLUSTER_MAX_CONC of cluster buy volume

    Score increases with:
      - number of participating insiders
      - total buy volume share
      - recency (linear decay: most-recent = 1.0, oldest in window = ~0.0)
    """
    ref = reference_date or datetime.utcnow()
    cutoff = ref - timedelta(days=CLUSTER_WINDOW_DAYS)

    buys = [
        t for t in _filter_transactions(transactions,
                                        lookback_days=CLUSTER_WINDOW_DAYS,
                                        reference_date=reference_date)
        if t["tx"] == "buy"
    ]

    if not buys:
        return 0.0, False

    # Check cluster conditions
    distinct_buyers = {t["insider_id"] for t in buys}
    n_insiders = len(distinct_buyers)
    n_trades   = len(buys)

    if n_insiders < CLUSTER_MIN_INSIDERS or n_trades < CLUSTER_MIN_TRADES:
        return 0.0, False

    # Concentration check
    total_buy_vol = sum(t["shares"] for t in buys)
    if total_buy_vol <= 0:
        return 0.0, False

    vol_by_insider: dict[str, float] = {}
    for t in buys:
        vol_by_insider[t["insider_id"]] = (
            vol_by_insider.get(t["insider_id"], 0.0) + t["shares"]
        )
    max_conc = max(vol_by_insider.values()) / total_buy_vol
    if max_conc >= CLUSTER_MAX_CONC:
        return 0.0, False

    # Cluster confirmed — score it
    window_span = float(CLUSTER_WINDOW_DAYS) or 1.0

    # Recency-weighted volume
    weighted_vol = 0.0
    for t in buys:
        age_days = (ref - t["date"]).days
        recency  = _clamp(1.0 - age_days / window_span, 0.0, 1.0)
        weighted_vol += t["shares"] * recency

    # Normalize: more insiders and higher recency-weighted vol → higher score
    insider_factor = _clamp((n_insiders - 1) / 4.0, 0.0, 1.0)  # saturates at 5+
    vol_factor     = _clamp(weighted_vol / (total_buy_vol + 1e-9), 0.0, 1.0)
    raw_score      = (insider_factor * 0.5 + vol_factor * 0.5) * 100.0

    return round(_clamp(raw_score, 0.0, 100.0), 2), True


# ── Metric 3: Insider Type Quality ───────────────────────────────────────────

def calc_insider_type_quality(
    transactions: list[dict],
    reference_date: datetime | None = None,
) -> float:
    """
    Weighted quality score (0-100) based on the seniority of insiders who bought.
    Higher-quality insiders (CEO/CFO/Director) have higher weight.
    Returns 50 (neutral) when no buys exist.
    """
    filtered = _filter_transactions(transactions, lookback_days=365,
                                    reference_date=reference_date)
    buys = [t for t in filtered if t["tx"] == "buy"]
    if not buys:
        return 50.0

    hq_vol = sum(t["shares"] for t in buys if _is_high_quality(t["role"]))
    total_vol = sum(t["shares"] for t in buys)

    if total_vol <= 0:
        return 50.0

    hq_fraction = hq_vol / total_vol  # 0–1

    # Map fraction to 0-100; pure HQ insiders → 100, zero HQ → 30 (not zero)
    score = 30.0 + hq_fraction * 70.0
    return round(_clamp(score, 0.0, 100.0), 2)


# ── Normalization helper ──────────────────────────────────────────────────────

def _norm_net_buying(net_pct: float) -> float:
    """
    Map net_insider_buying [-100, +100] to [0, 100].
    Center at 0 (→ 50), linear.
    """
    return _clamp(50.0 + net_pct * 0.5, 0.0, 100.0)


# ── Main entry point ──────────────────────────────────────────────────────────

def get_insider_score(
    ticker: str,
    transactions: list[dict],
    shares_outstanding: float | None = None,
    reference_date: datetime | None = None,
) -> dict:
    """
    Compute insider activity score from a list of insider transactions.

    Args:
        ticker:             Stock ticker (stored in output, not used for fetching).
        transactions:       List of insider transaction dicts (see module docstring).
        shares_outstanding: Float; used to normalize net buying. Falls back to
                            total traded volume in the window when absent.
        reference_date:     Reference datetime for recency calculations.
                            Defaults to utcnow().

    Returns strict dict (scorer.py compatible via total_score / total_max).
    """
    ticker = ticker.upper().strip()
    ref    = reference_date or datetime.utcnow()

    # Minimum coverage check: need at least one transaction in last 12 months
    recent = _filter_transactions(transactions, lookback_days=365,
                                  reference_date=ref)
    if not recent:
        result = dict(_NEUTRAL)
        result["ticker"] = ticker
        return result

    # Raw metrics
    net_buying = calc_net_insider_buying(
        transactions, shares_outstanding=shares_outstanding, reference_date=ref
    )
    cluster_score, cluster_detected = calc_cluster_buying_score(
        transactions, reference_date=ref
    )
    type_quality = calc_insider_type_quality(transactions, reference_date=ref)

    # Normalise net buying to 0-100 for weighted sum
    n_net = _norm_net_buying(net_buying)

    # Weighted composite
    raw = (
        n_net         * 0.40 +
        cluster_score * 0.40 +
        type_quality  * 0.20
    )
    insider_confidence_score = round(_clamp(raw, 0.0, 100.0), 2)

    # Diagnostic counts
    buys  = [t for t in recent if t["tx"] == "buy"]
    sells = [t for t in recent if t["tx"] == "sell"]

    return {
        "ticker":                  ticker,
        "net_insider_buying":      round(net_buying, 4),
        "cluster_buying_score":    round(cluster_score, 2),
        "insider_type_quality":    round(type_quality, 2),
        "insider_confidence_score": insider_confidence_score,
        "signal":                  _signal(insider_confidence_score),
        "n_buy_transactions":      len(buys),
        "n_sell_transactions":     len(sells),
        "n_distinct_buyers":       len({t["insider_id"] for t in buys}),
        "cluster_detected":        cluster_detected,
        "low_coverage":            len(recent) < 3,
        # scorer.py compatibility
        "total_score":             insider_confidence_score,
        "total_max":               100.0,
    }
