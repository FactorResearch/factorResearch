#!/usr/bin/env python3
"""
Wire insider_activity.py into the app.

Usage (run from project root):
    python apply_insider_wire.py
"""

from pathlib import Path


def patch(filepath: str, old: str, new: str) -> None:
    p = Path(filepath)
    if not p.exists():
        print(f"  ERROR : file not found — {filepath}")
        return
    content = p.read_text(encoding="utf-8")
    if old not in content:
        print(f"  SKIP  : pattern not found in {filepath}")
        return
    p.write_text(content.replace(old, new, 1), encoding="utf-8")
    print(f"  OK    : {filepath}")


# ── 1. codes/models/__init__.py ───────────────────────────────────────────────
patch(
    "codes/models/__init__.py",
    "from . import growth_quality",
    "from . import growth_quality\nfrom . import insider_activity",
)

# ── 2a. codes/__init__.py — models import list ────────────────────────────────
patch(
    "codes/__init__.py",
    "    profitability, fcf_quality, capital_allocation, growth_quality, regime,\n)",
    "    profitability, fcf_quality, capital_allocation, growth_quality, regime,\n"
    "    insider_activity,\n)",
)

# ── 2b. codes/__init__.py — _compat dict ──────────────────────────────────────
patch(
    "codes/__init__.py",
    "    'regime':               regime,\n}",
    "    'regime':               regime,\n"
    "    'insider_activity':     insider_activity,\n}",
)

# ── 3. codes/data/api_fetcher.py — insider fetch functions ───────────────────
_INSIDER_FETCHER = '''\
# ══════════════════════════════════════════════════════════════════════════════
# Insider transactions  — Finnhub only (no free-tier fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _fh_get_insider_transactions(symbol: str, years: int = 1) -> list[dict]:
    """Open-market insider transactions from Finnhub (codes P and S only)."""
    if not _fh_client:
        return []
    _fh_limiter.check()
    try:
        cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
        result = _fh_client.company_insider_transactions(
            symbol.upper(),
            _from=cutoff.strftime("%Y-%m-%d"),
            to=pd.Timestamp.now().strftime("%Y-%m-%d"),
        )
        _fh_limiter.record()
        out = []
        for item in (result.get("data") or []):
            code   = str(item.get("transactionCode", "")).strip().upper()
            change = float(item.get("change") or 0)
            if code == "P":
                tx, is_open = "buy",  True
            elif code == "S":
                tx, is_open = "sell", True
            elif change > 0:
                tx, is_open = "buy",  False
            elif change < 0:
                tx, is_open = "sell", False
            else:
                continue
            shares = abs(change)
            if shares <= 0:
                continue
            out.append({
                "date":           item.get("transactionDate") or item.get("filingDate", ""),
                "insider_id":     str(item.get("name", "unknown")),
                "role":           str(item.get("relationship", "")),
                "transaction":    tx,
                "shares":         shares,
                "is_open_market": is_open,
            })
        return out
    except RateLimitError:
        raise
    except Exception as e:
        print(f"  [Finnhub] insider_transactions error for {symbol}: {e}")
        return []


def get_insider_transactions(symbol: str, years: int = 1) -> list[dict]:
    """
    Insider transaction history (cached).
    Returns list compatible with insider_activity.get_insider_score().
    Empty list when Finnhub key is absent.
    """
    symbol = symbol.upper().strip()
    cached = read("insiders", symbol)
    if cached is not None:
        return cached
    transactions = _fh_get_insider_transactions(symbol, years) if _fh_client else []
    write("insiders", symbol, transactions)
    return transactions


'''

# The diagnostics section header is the unique anchor
_DIAG_ANCHOR = (
    "# ══════════════════════════════════════════════════════════════════════════════\n"
    "# Diagnostics\n"
    "# ══════════════════════════════════════════════════════════════════════════════\n"
)

patch(
    "codes/data/api_fetcher.py",
    _DIAG_ANCHOR,
    _INSIDER_FETCHER + _DIAG_ANCHOR,
)

# ── 4. codes/app.py — extend models import ────────────────────────────────────
patch(
    "codes/app.py",
    "capital_allocation as capital_allocation_model, regime as regime_model",
    "capital_allocation as capital_allocation_model, regime as regime_model,"
    " insider_activity as insider_activity_model",
)

# ── 5. codes/app.py — call insider_activity in analyze_stock() ───────────────
_INSIDER_CALL = '''\
    # Insider Activity (P4)
    insider_activity_result = None
    try:
        transactions = api_fetcher.get_insider_transactions(symbol)
        shares_out = None
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
    # Enhanced 9-factor composite
    enhanced = scorer.enhanced_composite('''

patch(
    "codes/app.py",
    "    # Enhanced 9-factor composite\n    enhanced = scorer.enhanced_composite(",
    _INSIDER_CALL,
)

# ── 6. codes/app.py — add to result dict ─────────────────────────────────────
patch(
    "codes/app.py",
    '        "capital_allocation": capital_allocation_result,\n        "regime":             regime_result,',
    '        "capital_allocation": capital_allocation_result,\n'
    '        "insider_activity":   insider_activity_result,\n'
    '        "regime":             regime_result,',
)

# ── 7. codes/app.py — add _insider_activity_card display helper ───────────────
_INSIDER_CARD = '''\
def _insider_activity_card(data: dict) -> html.Div:
    """Insider buying/selling activity card."""
    ia = data.get("insider_activity") or {}
    if not ia or ia.get("low_coverage"):
        return html.Div()
    score  = ia.get("insider_confidence_score")
    signal = ia.get("signal", "NEUTRAL")
    if score is None:
        return html.Div()
    sig_color = {"BULLISH": GREEN, "NEUTRAL": AMBER, "BEARISH": RED}.get(signal, MUTED)

    def _fmt(v, fmt=".2f", suffix=""):
        return f"{v:{fmt}}{suffix}" if v is not None else "N/A"

    cluster_txt = "\\u2705 Detected" if ia.get("cluster_detected") else "\\u2014"
    metrics = [
        ("Net Insider Buying",  _fmt(ia.get("net_insider_buying"),  "+.2f", "%")),
        ("Cluster Buying",      cluster_txt),
        ("Type Quality Score",  _fmt(ia.get("insider_type_quality"), ".1f", "/100")),
        ("Buy Transactions",    str(ia.get("n_buy_transactions",  0))),
        ("Sell Transactions",   str(ia.get("n_sell_transactions", 0))),
        ("Distinct Buyers",     str(ia.get("n_distinct_buyers",   0))),
    ]
    rows = [
        html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "padding": "4px 0", "borderBottom": f"1px solid {BORDER}", "fontSize": "12px",
        }, children=[
            html.Span(lbl, className="text-muted"),
            html.Span(val, style={"color": TEXT, "fontWeight": "600"}),
        ])
        for lbl, val in metrics
    ]
    return html.Div(className="scorecard", children=[
        html.Div(style={
            "display": "flex", "alignItems": "center",
            "gap": "10px", "padding": "14px 18px 10px",
        }, children=[
            html.Span("Insider Activity",
                      style={"fontSize": "14px", "fontWeight": "700", "color": TEXT}),
            html.Span(f"{score:.0f}/100",
                      style={"fontSize": "22px", "fontWeight": "800", "color": sig_color}),
            html.Span(f"\\u2014 {signal}",
                      style={"fontSize": "13px", "color": sig_color}),
        ]),
        html.Div(rows, className="px-xl pb-2xl"),
    ])


'''

patch(
    "codes/app.py",
    'def _piotroski_card(data: dict) -> html.Div:\n    """Piotroski F-Score card',
    _INSIDER_CARD + 'def _piotroski_card(data: dict) -> html.Div:\n    """Piotroski F-Score card',
)

# ── 8. codes/app.py — render card in _build_analysis_content() ───────────────
patch(
    "codes/app.py",
    '        html.Div(className="card-row", children=capital_allocation_card),',
    '        html.Div(className="card-row", children=[capital_allocation_card, _insider_activity_card(data)]),',
)

print("\nAll patches applied.")