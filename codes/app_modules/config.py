"""Shared constants and lightweight validation helpers for the Dash app."""

import re

# ── Color Theme ────────────────────────────────────────────────────────────────
DARK, CARD, BORDER, GREEN, RED, AMBER, BLUE, TEXT, MUTED ,WHITE= (
    "#0d1117", "#1e2a3a", "#1e2a3a", "#00e676", "#ff1744",
    "#ffab00", "#1677ff", "#e8eaf0", "#4a5568", "#ffffff"
)

# SECURITY (ISSUE_010 / NEW-1 / NEW-5): allow-list validation at every
# input boundary that reaches a cache key or an outbound API URL.
TICKER_RE = re.compile(r"^[A-Z]{1,6}(\.[A-Z])?$")
PORTFOLIO_NAME_RE = re.compile(r"^[A-Za-z0-9 _-]{1,32}$")


def validate_ticker(raw: str) -> str | None:
    t = (raw or "").strip().upper()
    return t if TICKER_RE.match(t) else None


def validate_portfolio_name(raw: str) -> str | None:
    n = (raw or "").strip()
    return n if PORTFOLIO_NAME_RE.match(n) else None


PAGE_SIZE = 20  # rows per page in screener table
# ── Moat grade tooltips (shown on hover in Buffett badge) ────────────────────
_MOAT_TOOLTIPS = {
    "A": (
        "Wide Moat (A) — The company has a durable, difficult-to-replicate competitive "
        "advantage that can protect earnings and returns for 10–20+ years. Examples include "
        "strong brands, network effects, high switching costs, cost leadership, or regulatory "
        "advantages. Consistently earns ROE ≥15%, maintains high margins, generates strong "
        "free cash flow, and is trading at or below its estimated intrinsic value."
    ),
    "B": (
        "Narrow Moat (B) — The company has a meaningful competitive advantage, but one that "
        "requires continued execution and reinvestment to sustain. It produces above-average "
        "returns and healthy profitability but faces stronger competitive pressure than the "
        "highest-quality businesses. A solid long-term holding when purchased at a reasonable valuation."
    ),
    "C": (
        "No Clear Moat (C) — The company operates in a highly competitive or commoditized "
        "industry without a durable structural advantage. Returns on capital and profitability "
        "tend to be average or inconsistent. While a sufficiently low price can improve future "
        "returns, long-term investors generally prefer outstanding businesses purchased at fair "
        "valuations over average businesses bought simply because they appear cheap."
    ),
    "D": (
        "Avoid (D) — The company shows multiple warning signs, such as weak or declining "
        "profitability, low returns on equity, excessive debt, poor cash generation, or a "
        "market price well above estimated intrinsic value. Successful long-term investing "
        "focuses first on preserving capital by avoiding low-quality businesses and significant "
        "overpayment."
    ),
}

def get_score_class(pct: float) -> str:
    """CSS class for score coloring."""
    if pct >= 65:
        return "high"
    elif pct >= 35:
        return "medium"
    else:
        return "low"

def get_verdict_class(label: str) -> str:
    """CSS class for verdict coloring."""
    return label.lower().replace(" ", "-") if label else "pending"
