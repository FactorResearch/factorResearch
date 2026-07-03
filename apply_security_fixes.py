#!/usr/bin/env python3
"""
Apply Phase 0/1 security fixes by exact-string anchor replacement.
Run from the repo root: python3 apply_security_fixes.py

Safer than a line-based patch because it doesn't depend on line numbers —
each fix only applies if its exact anchor text is found in the target file.
If an anchor doesn't match (e.g. the file has since changed), that fix is
skipped and reported so you can apply it manually.
"""
import re
import sys
from pathlib import Path

FIXES = []  # list of (filepath, old, new, label)


def fix(filepath, old, new, label):
    FIXES.append((filepath, old, new, label))


# ── codes/data/cache.py — NEW-1: path traversal ──────────────────────────────
fix(
    "codes/data/cache.py",
    'import json\nimport math\nimport os\nimport time\nfrom pathlib import Path',
    'import json\nimport math\nimport os\nimport re\nimport time\nfrom pathlib import Path',
    "cache.py: add re import",
)
fix(
    "codes/data/cache.py",
    'def _path(kind: str, key: str) -> Path:\n    return CACHE_DIR / f"{kind}-{key.lower()}.json"',
    'def _path(kind: str, key: str) -> Path:\n'
    '    key = key.lower()\n'
    '    if ".." in key or "/" in key or "\\\\" in key or not _SAFE_KEY_RE.match(key):\n'
    '        raise ValueError(f"Unsafe cache key rejected: {key!r}")\n'
    '    return CACHE_DIR / f"{kind}-{key}.json"',
    "cache.py: sanitize _path()",
)
fix(
    "codes/data/cache.py",
    'CACHE_DIR.mkdir(exist_ok=True)\n\n\ndef _path',
    'CACHE_DIR.mkdir(exist_ok=True)\n\n'
    '# SECURITY (NEW-1): cache keys become filenames — enforce an allow-list\n'
    '# as a hard backstop against path traversal.\n'
    '_SAFE_KEY_RE = re.compile(r"^[a-z0-9_.-]{1,200}$")\n\n\ndef _path',
    "cache.py: add _SAFE_KEY_RE",
)

# ── codes/engine/screener.py — ISSUE_014: unbounded _user_progress ─────────
fix(
    "codes/engine/screener.py",
    '_user_progress: dict[str, dict] = {}\n_user_progress_lock = threading.Lock()',
    '_user_progress: dict[str, dict] = {}\n_user_progress_lock = threading.Lock()\n'
    '_USER_PROGRESS_TTL = 30 * 60  # seconds (ISSUE_014)',
    "screener.py: add TTL constant",
)
fix(
    "codes/engine/screener.py",
    '    with _lock:\n        snapshot = dict(_progress)\n'
    '    if session_id:\n        with _user_progress_lock:\n'
    '            _user_progress[session_id] = snapshot\n    return snapshot',
    '    with _lock:\n        snapshot = dict(_progress)\n'
    '    if session_id:\n        with _user_progress_lock:\n'
    '            _user_progress[session_id] = {"data": snapshot, "ts": time.time()}\n'
    '            _sweep_user_progress_locked()\n    return snapshot\n\n\n'
    'def _sweep_user_progress_locked() -> None:\n'
    '    """Evict stale per-session snapshots (ISSUE_014). Caller holds the lock."""\n'
    '    cutoff = time.time() - _USER_PROGRESS_TTL\n'
    '    stale = [sid for sid, entry in _user_progress.items() if entry["ts"] < cutoff]\n'
    '    for sid in stale:\n        _user_progress.pop(sid, None)',
    "screener.py: TTL sweep in get_progress",
)

# ── codes/app.py ──────────────────────────────────────────────────────────
fix(
    "codes/app.py",
    "import traceback\nimport sys\nimport os\nimport math",
    "import traceback\nimport sys\nimport os\nimport re\nimport math",
    "app.py: add re import",
)
fix(
    "codes/app.py",
    'server = app.server\nserver.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24)\n'
    '@server.after_request\ndef _log_errors(response):\n    return response',
    'server = app.server\n\n'
    '# SECURITY (NEW-7): require a real secret key in production instead of\n'
    '# silently falling back to a random one.\n'
    '_FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")\n'
    'if not _FLASK_SECRET_KEY:\n'
    '    if os.environ.get("APP_ENV") == "production":\n'
    '        sys.exit("FATAL: FLASK_SECRET_KEY must be set in production.")\n'
    '    _FLASK_SECRET_KEY = os.urandom(24)\n'
    'server.secret_key = _FLASK_SECRET_KEY\n'
    'server.config.update(\n'
    '    SESSION_COOKIE_SECURE=os.environ.get("APP_ENV") == "production",\n'
    '    SESSION_COOKIE_HTTPONLY=True,\n'
    '    SESSION_COOKIE_SAMESITE="Lax",\n'
    ')\n\n'
    '# SECURITY (NEW-3): baseline security headers on every response.\n'
    '@server.after_request\n'
    'def _apply_security_headers(response):\n'
    '    response.headers.setdefault("X-Content-Type-Options", "nosniff")\n'
    '    response.headers.setdefault("X-Frame-Options", "DENY")\n'
    '    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")\n'
    '    if os.environ.get("APP_ENV") == "production":\n'
    '        response.headers.setdefault(\n'
    '            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"\n'
    '        )\n'
    '    return response',
    "app.py: harden secret key/session cookie + security headers",
)
fix(
    "codes/app.py",
    'DARK, CARD, BORDER, GREEN, RED, AMBER, BLUE, TEXT, MUTED ,WHITE= (\n'
    '    "#0f1117", "#1a1d27", "#2a2d3e", "#00c853", "#ff1744",\n'
    '    "#ffc107", "#448aff", "#e0e0e0", "#9e9e9e", "#ffffff"\n'
    ')\nPAGE_SIZE = 20  # rows per page in screener table',
    'DARK, CARD, BORDER, GREEN, RED, AMBER, BLUE, TEXT, MUTED ,WHITE= (\n'
    '    "#0f1117", "#1a1d27", "#2a2d3e", "#00c853", "#ff1744",\n'
    '    "#ffc107", "#448aff", "#e0e0e0", "#9e9e9e", "#ffffff"\n'
    ')\n\n'
    '# SECURITY (ISSUE_010 / NEW-1 / NEW-5): allow-list validation at every\n'
    '# input boundary that reaches a cache key or an outbound API URL.\n'
    'TICKER_RE = re.compile(r"^[A-Z]{1,6}(\\.[A-Z])?$")\n'
    'PORTFOLIO_NAME_RE = re.compile(r"^[A-Za-z0-9 _-]{1,32}$")\n\n\n'
    'def validate_ticker(raw: str) -> str | None:\n'
    '    t = (raw or "").strip().upper()\n'
    '    return t if TICKER_RE.match(t) else None\n\n\n'
    'def validate_portfolio_name(raw: str) -> str | None:\n'
    '    n = (raw or "").strip()\n'
    '    return n if PORTFOLIO_NAME_RE.match(n) else None\n\n\n'
    'PAGE_SIZE = 20  # rows per page in screener table',
    "app.py: add validate_ticker / validate_portfolio_name",
)
fix(
    "codes/app.py",
    'global _analysis_cache, _analysis_cache_lock\n    \n'
    '    symbol = symbol.upper().strip()\n'
    '    # 1A: Check in-memory cache first (zero disk I/O for repeat lookups)',
    'global _analysis_cache, _analysis_cache_lock\n\n'
    '    symbol = validate_ticker(symbol)\n'
    '    if not symbol:\n'
    '        return {"error": "Invalid ticker format."}\n'
    '    # 1A: Check in-memory cache first (zero disk I/O for repeat lookups)',
    "app.py: validate ticker in analyze_stock()",
)
fix(
    "codes/app.py",
    '    except Exception as e:\n        return {"error": f"SEC EDGAR error: {e}"}',
    '    except Exception as e:\n'
    '        print(f"[SEC EDGAR error] {symbol}: {e}")  # full detail server-side only\n'
    '        return {"error": "Could not retrieve data for this ticker. Please try again shortly."}',
    "app.py: stop leaking exception text (NEW-6)",
)
fix(
    "codes/app.py",
    '    if not ticker or not ticker.strip():\n'
    '        return [], None, "❌ Please enter a ticker symbol.", False, False, dash.no_update, {"display": "none"}, None, dash.no_update\n'
    '    symbol = ticker.strip().upper()\n    result = analyze_stock(symbol)',
    '    if not ticker or not ticker.strip():\n'
    '        return [], None, "❌ Please enter a ticker symbol.", False, False, dash.no_update, {"display": "none"}, None, dash.no_update\n'
    '    symbol = validate_ticker(ticker)\n'
    '    if not symbol:\n'
    '        return [], None, "❌ Invalid ticker format (letters only, max 6 chars).", False, False, dash.no_update, {"display": "none"}, None, dash.no_update\n'
    '    result = analyze_stock(symbol)',
    "app.py: validate ticker in run_analysis()",
)
fix(
    "codes/app.py",
    'def create_portfolio(n, name, refresh):\n'
    '    if not n:\n        return dash.no_update, dash.no_update, "", ""\n'
    '    name = (name or "").strip()\n'
    '    if not name:\n'
    '        return dash.no_update, dash.no_update, "❌ Please enter a name.", dash.no_update',
    'def create_portfolio(n, name, refresh):\n'
    '    if not n:\n        return dash.no_update, dash.no_update, "", ""\n'
    '    name = validate_portfolio_name(name)\n'
    '    if not name:\n'
    '        return dash.no_update, dash.no_update, "❌ Invalid name (letters, numbers, spaces, - or _, max 32 chars).", dash.no_update',
    "app.py: validate portfolio name in create_portfolio()",
)
fix(
    "codes/app.py",
    '    # Resolve portfolio name\n    port_name = (new_name or "").strip() or selected',
    '    # Resolve portfolio name\n    port_name = validate_portfolio_name(new_name) or selected',
    "app.py: validate portfolio name in add_to_portfolio()",
)
fix(
    "codes/app.py",
    '            html.P("Orthogonal factor score: Value, Quality, Momentum, Profitability, FCF Quality, Earnings Revisions, Capital Allocation, Growth Quality, Risk, and Altman.")\n        ])\n    ]),',
    '            html.P("Orthogonal factor score: Value, Quality, Momentum, Profitability, FCF Quality, Earnings Revisions, Capital Allocation, Growth Quality, Risk, and Altman."),\n'
    '            html.P(\n'
    '                "Not financial advice. For informational purposes only. "\n'
    '                "See Terms of Service and Privacy Policy.",\n'
    '                style={"fontSize": "11px", "color": "#9e9e9e", "marginTop": "4px"}\n'
    '            ),\n        ])\n    ]),',
    "app.py: add ToS/disclaimer line under header (ISSUE_013)",
)
fix(
    "codes/app.py",
    '    # Stores\n    dcc.Store(id="screener-cache"),',
    '    # Legal footer (ISSUE_013) — routes are placeholders until ToS/Privacy pages exist.\n'
    '    html.Div(className="app-footer", style={\n'
    '        "textAlign": "center", "padding": "16px", "fontSize": "11px", "color": "#9e9e9e"\n'
    '    }, children=[\n'
    '        html.Span("© Intrinsic IQ · "),\n'
    '        html.A("Terms of Service", href="/terms", style={"color": "#9e9e9e"}),\n'
    '        html.Span(" · "),\n'
    '        html.A("Privacy Policy", href="/privacy", style={"color": "#9e9e9e"}),\n'
    '        html.Span(" · Not financial advice."),\n'
    '    ]),\n\n'
    '    # Stores\n    dcc.Store(id="screener-cache"),',
    "app.py: add legal footer",
)
fix(
    "codes/app.py",
    '    _portfolio_cache_by_session[sid] = {"symbols": result, "ts": _t.time()}\n    return result',
    '    _portfolio_cache_by_session[sid] = {"symbols": result, "ts": _t.time()}\n'
    '    # ISSUE_014: bound unbounded growth of this per-session cache.\n'
    '    stale_cutoff = _t.time() - 3600\n'
    '    for stale_sid in [s for s, e in _portfolio_cache_by_session.items()\n'
    '                      if e["ts"] < stale_cutoff]:\n'
    '        _portfolio_cache_by_session.pop(stale_sid, None)\n'
    '    return result',
    "app.py: TTL sweep for _portfolio_cache_by_session (ISSUE_014)",
)
fix(
    "codes/app.py",
    'startup()\nif __name__ == "__main__":\n'
    '    app.run(host="0.0.0.0",debug=True, port=8050)',
    'startup()\nif __name__ == "__main__":\n'
    '    # SECURITY (NEW-2): never bind debug=True to a public interface.\n'
    '    _is_prod = os.environ.get("APP_ENV") == "production"\n'
    '    app.run(host="0.0.0.0" if _is_prod else "127.0.0.1",\n'
    '            debug=not _is_prod, port=8050)',
    "app.py: disable debug mode / restrict bind address in prod (NEW-2)",
)


def main():
    root = Path(".").resolve()
    ok, failed = 0, 0
    for filepath, old, new, label in FIXES:
        p = root / filepath
        if not p.exists():
            print(f"[SKIP] {label} — file not found: {filepath}")
            failed += 1
            continue
        text = p.read_text()
        if old not in text:
            if new in text:
                print(f"[SKIP] {label} — already applied")
                ok += 1
                continue
            print(f"[FAIL] {label} — anchor text not found in {filepath}")
            print("        Apply this one manually; see phase0-1-security-fixes.patch for the diff.")
            failed += 1
            continue
        if text.count(old) > 1:
            print(f"[WARN] {label} — anchor appears {text.count(old)} times, replacing first occurrence only")
            text = text.replace(old, new, 1)
        else:
            text = text.replace(old, new)
        p.write_text(text)
        print(f"[OK]   {label}")
        ok += 1

    print(f"\n{ok} applied/already-present, {failed} need manual review.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
