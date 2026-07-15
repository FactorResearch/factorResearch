"""
Portfolio builder engine.

Storage layout (via cache.py):
  cache key: ("portfolio", "index")   → list of portfolio names
  cache key: ("portfolio", name)      → portfolio dict (see schema below)

Portfolio schema:
  {
    "name":     str,
    "created":  ISO timestamp,
    "holdings": {
      "AAPL": {
        "shares":       10,           # shares at time of purchase (pre-split)
        "price_at_add": 182.50,       # price when added (used for cost basis)
        "name":         "Apple Inc.",
        "added_date":   "2024-01-15", # anchors split lookups; present on new holdings
      },
      ...
    }
  }

Simulation output:
  backtest  — monthly portfolio value vs SPY over 10 years (actual prices)
  montecarlo — 2-year forward projection: 1,000 paths → p10/p50/p90 bands
"""

import time
import datetime
import hashlib
import numpy as np
import pandas as pd
from codes.core import financial_math as fm
from .data import cache
from .data import api_fetcher

MAX_HOLDINGS  = 10
MIN_SHARES    = 5
MC_PATHS      = 1000
MC_YEARS      = 2
MC_MONTHS     = MC_YEARS * 12

# ── In-process split cache (lives for the server session, refreshed every 6h) ─
# Avoids re-fetching the same symbol's splits on every backtest call.
_splits_memo: dict[str, tuple[float, list]] = {}
_SPLITS_TTL  = 6 * 3600   # seconds


def _splits_since(symbol: str, since_date: str) -> list[dict]:
    """
    Return splits for `symbol` that occurred on or after `since_date` (YYYY-MM-DD).
    Uses an in-process memo so the same symbol isn't re-fetched within a session.
    """
    now = time.time()
    if symbol in _splits_memo:
        ts, data = _splits_memo[symbol]
        if now - ts < _SPLITS_TTL:
            splits = data
        else:
            splits = api_fetcher.get_splits(symbol)
            _splits_memo[symbol] = (now, splits)
    else:
        splits = api_fetcher.get_splits(symbol)
        _splits_memo[symbol] = (now, splits)

    return [s for s in splits if s["date"] >= since_date]


def _split_factor_at(splits: list[dict], as_of: pd.Timestamp) -> float:
    """
    Cumulative split factor from a pre-filtered splits list (already
    filtered to since_date) up to and including `as_of` date.

    Example: 2:1 split on 2020-06-01, then 3:1 on 2022-01-15.
      as_of = 2021-12-31  →  factor = 2.0
      as_of = 2023-01-01  →  factor = 6.0
    """
    factor = 1.0
    for split in splits:
        if pd.Timestamp(split["date"]) <= as_of:
            factor *= split["ratio"]
    return factor


def get_cumulative_split_factor(symbol: str, since_date: str) -> float:
    """
    Public helper: cumulative split factor for `symbol` from `since_date`
    up to today.  Multiply the original share count by this number to get
    the current split-adjusted share count.
    """
    splits = _splits_since(symbol, since_date)
    today  = pd.Timestamp.today().normalize()
    return _split_factor_at(splits, today)

# ══════════════════════════════════════════════════════════════════════════════
# Storage helpers
# ══════════════════════════════════════════════════════════════════════════════

def _cache_token(value: str) -> str:
    """Stable filename-safe token for user-controlled cache key parts."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _portfolio_index_key(user_id: str) -> str:
    return f"u_{_cache_token(user_id)}_index"


def _portfolio_key(user_id: str, name: str) -> str:
    return f"u_{_cache_token(user_id)}_p_{_cache_token(name)}"


def _simulation_key(user_id: str, portfolio_name: str) -> str:
    return f"u_{_cache_token(user_id)}_sim_{_cache_token(portfolio_name)}"


def _legacy_index_key(user_id: str) -> str:
    return f"{user_id}_index"


def _legacy_portfolio_key(user_id: str, name: str) -> str:
    return f"{user_id}_p_{name}"


def _legacy_simulation_key(user_id: str, portfolio_name: str) -> str:
    return f"{user_id}_{portfolio_name}"


def _write_cache_or_raise(kind: str, key: str, data) -> None:
    if cache.write(kind, key, data) is False:
        raise RuntimeError(f"Failed to write cache entry {kind}:{key}")


def _clear_cache_if_safe(kind: str, key: str) -> None:
    try:
        cache.clear(kind, key)
    except ValueError:
        pass


def _read_cache_if_safe(kind: str, key: str):
    try:
        return cache.read(kind, key)
    except ValueError:
        return None


def _load_index(user_id: str) -> list[str]:
    encoded = cache.read("portfolio", _portfolio_index_key(user_id))
    if encoded is not None:
        return encoded
    return _read_cache_if_safe("portfolio", _legacy_index_key(user_id)) or []


def _save_index(user_id: str, names: list[str]) -> None:
    _write_cache_or_raise("portfolio", _portfolio_index_key(user_id), names)


def list_portfolios(user_id: str) -> list[str]:
    return _load_index(user_id)


def load_portfolio(user_id: str, name: str) -> dict | None:
    encoded = cache.read("portfolio", _portfolio_key(user_id, name))
    if encoded is not None:
        return encoded
    return _read_cache_if_safe("portfolio", _legacy_portfolio_key(user_id, name))


def save_portfolio(user_id: str, portfolio: dict) -> None:
    name = portfolio["name"]
    _write_cache_or_raise("portfolio", _portfolio_key(user_id, name), portfolio)
    idx = _load_index(user_id)
    if name not in idx:
        idx.append(name)
        _save_index(user_id, idx)


def delete_portfolio(user_id: str, name: str) -> None:
    _clear_cache_if_safe("portfolio", _portfolio_key(user_id, name))
    _clear_cache_if_safe("portfolio", _legacy_portfolio_key(user_id, name))
    idx = [n for n in _load_index(user_id) if n != name]
    _save_index(user_id, idx)


def create_portfolio(user_id: str, name: str) -> dict:
    p = {
        "name":     name,
        "created":  datetime.datetime.now().isoformat(),
        "holdings": {},
    }
    save_portfolio(user_id, p)
    return p

# ══════════════════════════════════════════════════════════════════════════════
# Holdings management
# ══════════════════════════════════════════════════════════════════════════════

def add_holding(user_id: str, name: str, symbol: str, shares: int,
                current_price: float, company_name: str) -> tuple[dict, str]:
    p = load_portfolio(user_id, name)
    if p is None:
        return {}, f'Portfolio "{name}" not found'

    symbol = symbol.upper().strip()

    if symbol in p["holdings"]:
        return p, f"{symbol} is already in this portfolio"

    if len(p["holdings"]) >= MAX_HOLDINGS:
        return p, f"Portfolio is full ({MAX_HOLDINGS} stocks maximum)"

    if shares < MIN_SHARES:
        return p, f"Minimum {MIN_SHARES} shares per stock (got {shares})"

    p["holdings"][symbol] = {
        "shares":       shares,
        "price_at_add": current_price,
        "name":         company_name,
        "added_date":   datetime.date.today().isoformat(),
    }
    save_portfolio(user_id, p)
    return p, ""


def remove_holding(user_id: str, name: str, symbol: str) -> tuple[dict, str]:
    p = load_portfolio(user_id, name)
    if p is None:
        return {}, f'Portfolio "{name}" not found'
    symbol = symbol.upper().strip()
    if symbol not in p["holdings"]:
        return p, f"{symbol} is not in this portfolio"
    del p["holdings"][symbol]
    save_portfolio(user_id, p)
    return p, ""
# ══════════════════════════════════════════════════════════════════════════════
# Simulation helpers
# ══════════════════════════════════════════════════════════════════════════════

def _load_history(symbol: str) -> pd.DataFrame:
    """Return monthly price history as a DataFrame with Date + Close."""
    df = api_fetcher.get_price_history(symbol, years=10)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["Date"]  = pd.to_datetime(df["Date"])
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna().sort_values("Date").reset_index(drop=True)
    return df


def _align_histories(histories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Inner-join all symbol histories on Date, keeping only dates present
    in every series.  Returns a wide DataFrame: Date + one col per symbol.
    """
    dfs = []
    for sym, df in histories.items():
        dfs.append(df.set_index("Date")["Close"].rename(sym))

    if not dfs:
        return pd.DataFrame()

    combined = pd.concat(dfs, axis=1).dropna()
    combined = combined.reset_index()
    combined = combined.rename(columns={"index": "Date"})
    return combined.sort_values("Date").reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# Backtest
# ══════════════════════════════════════════════════════════════════════════════

def run_backtest(portfolio: dict) -> dict:
    """
    Compute monthly portfolio value vs SPY over 10 years.

    Entry: shares × price at the FIRST date available in the aligned history.
    This is the same entry date for every holding and for SPY, making the
    comparison fair.

    Returns:
      {
        "dates":           [str, ...],          # monthly ISO dates
        "portfolio_value": [float, ...],        # $ value each month
        "spy_value":       [float, ...],        # $ value if same $ → SPY
        "total_invested":  float,               # shares × first-month price
        "spy_invested":    float,               # same dollar amount
        "final_value":     float,
        "final_spy":       float,
        "cagr":            float,               # annualised % return
        "spy_cagr":        float,
        "holdings_detail": { SYM: {shares, entry_price, current_price, gain_pct} }
        "error":           str | None,
      }
    """
    holdings = portfolio.get("holdings", {})
    if not holdings:
        return {"error": "Portfolio is empty"}

    symbols = list(holdings.keys())

    # Load all histories + SPY
    print(f"  [Backtest] loading {len(symbols)+1} price histories...")
    histories = {}
    for sym in symbols + ["SPY"]:
        h = _load_history(sym)
        if not h.empty:
            histories[sym] = h

    missing = [s for s in symbols if s not in histories]
    if missing:
        print(f"  [Backtest] ⚠️  No price history for: {missing}")

    available = [s for s in symbols if s in histories]
    if not available or "SPY" not in histories:
        return {"error": "Not enough price history to run backtest"}

    # Align on common dates
    to_align = {s: histories[s] for s in available + ["SPY"]}
    wide = _align_histories(to_align)
    if wide.empty or len(wide) < 6:
        return {"error": "Insufficient overlapping price history"}

    # Pre-fetch split histories for every available symbol.
    # Falls back to the portfolio created date for legacy holdings that
    # pre-date the added_date field.
    port_created = portfolio.get("created", "2000-01-01")[:10]
    splits_by_sym: dict[str, list[dict]] = {}
    for sym in available:
        h        = holdings[sym]
        since    = h.get("added_date") or port_created
        splits_by_sym[sym] = _splits_since(sym, since)

    # Entry values at first date — apply any splits that already happened
    # between the holding's added_date and the first date in price history.
    entry_row = wide.iloc[0]
    entry_date = entry_row["Date"]
    port_entry_value = sum(
        holdings[s]["shares"]
        * _split_factor_at(splits_by_sym[s], entry_date)
        * float(entry_row[s])
        for s in available if s in wide.columns
    )

    spy_entry_price  = float(entry_row["SPY"])
    spy_shares_equiv = port_entry_value / spy_entry_price  # same $ in SPY

    # Monthly values — share count adjusts forward as each split date passes.
    dates = wide["Date"].dt.strftime("%Y-%m-%d").tolist()
    port_values = []
    spy_values  = []

    for _, row in wide.iterrows():
        row_date = row["Date"]
        pv = sum(
            holdings[s]["shares"]
            * _split_factor_at(splits_by_sym[s], row_date)
            * float(row[s])
            for s in available if s in wide.columns
        )
        port_values.append(round(pv, 2))
        spy_values.append(round(spy_shares_equiv * float(row["SPY"]), 2))

   # CAGR
    first_date = wide["Date"].iloc[0]
    last_date  = wide["Date"].iloc[-1]
    n_years    = max((last_date - first_date).days / 365.25, 1 / 12)

    port_cagr_raw = fm.cagr(port_values[0], port_values[-1], n_years)
    spy_cagr_raw = fm.cagr(spy_values[0], spy_values[-1], n_years)
    port_cagr = port_cagr_raw * 100 if port_cagr_raw is not None else 0.0
    spy_cagr = spy_cagr_raw * 100 if spy_cagr_raw is not None else 0.0

    # Per-holding detail — shares and current_value use fully split-adjusted count.
    last_row  = wide.iloc[-1]
    last_date = last_row["Date"]
    holdings_detail = {}
    for s in available:
        if s not in wide.columns:
            continue
        ep = float(entry_row[s])
        cp = float(last_row[s])

        # Cumulative split factor from purchase date through end of backtest
        factor     = _split_factor_at(splits_by_sym[s], last_date)
        adj_shares = holdings[s]["shares"] * factor

        gain = (cp - ep) / ep * 100 if ep > 0 else 0

        holdings_detail[s] = {
            "shares":          round(adj_shares),        # split-adjusted count
            "original_shares": holdings[s]["shares"],    # as-stored (pre-split)
            "split_factor":    round(factor, 4),         # e.g. 20.0 for one 20:1 split
            "splits":          splits_by_sym[s],         # list of individual split events
            "entry_price":     round(ep, 2),
            "current_price":   round(cp, 2),
            "gain_pct":        round(gain, 1),
            "current_value":   round(adj_shares * cp, 2),
        }

    return {
        "dates":            dates,
        "portfolio_value":  port_values,
        "spy_value":        spy_values,
        "total_invested":   round(port_entry_value, 2),
        "spy_invested":     round(port_entry_value, 2),
        "final_value":      round(port_values[-1], 2),
        "final_spy":        round(spy_values[-1], 2),
        "cagr":             round(port_cagr, 2),
        "spy_cagr":         round(spy_cagr, 2),
        "n_months":         len(wide),
        "holdings_detail":  holdings_detail,
        "error":            None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Monte Carlo projection
# ══════════════════════════════════════════════════════════════════════════════

def run_montecarlo(portfolio: dict, backtest: dict) -> dict:
    """
    2-year forward Monte Carlo using per-stock historical monthly returns
    with full covariance-derived correlation matrix (multivariate simulation).
    """
    holdings = portfolio.get("holdings", {})
    if not holdings:
        return {"error": "Portfolio is empty"}

    if backtest.get("error"):
        start_value = sum(
            h["shares"] * h["price_at_add"]
            for h in holdings.values()
        )
    else:
        start_value = backtest["final_value"]

    if start_value <= 0:
        return {"error": "Cannot project from zero or negative portfolio value"}

    symbols = list(holdings.keys())

    # Load returns for covariance
    ret_series: dict[str, pd.Series] = {}
    weights: dict[str, float] = {}
    total_val = 0.0

    for sym, h in holdings.items():
        price = h.get("price_at_add", 0)
        val = h["shares"] * price
        total_val += val

    for sym in symbols:
        df = _load_history(sym)
        if not df.empty and len(df) >= 12:
            rets = df["Close"].pct_change().dropna()
            ret_series[sym] = rets
        else:
            # fallback
            ret_series[sym] = pd.Series([0.006] * 60)  # dummy

        price = holdings[sym].get("price_at_add", 1)
        val = holdings[sym]["shares"] * price
        weights[sym] = val / total_val if total_val > 0 else 1 / len(symbols)

    # ── Build correlation matrix from covariance (ensures symmetry) ──
    valid_syms = [s for s in symbols if len(ret_series[s]) > 1]
    if len(valid_syms) >= 2:
        ret_df = pd.concat([ret_series[s].rename(s) for s in valid_syms], axis=1).dropna()
        corr_mat = fm.correlation_matrix(ret_df.values)
        if corr_mat is None:
            corr_mat = ret_df.corr().values  # fallback for degenerate inputs
        stds = ret_df.std().values
        cov_mat = np.diag(stds) @ corr_mat @ np.diag(stds)  # full covariance
    else:
        # fallback to independent
        corr_mat = np.eye(len(symbols))
        stds = np.array([ret_series[s].std() if len(ret_series[s]) > 1 else 0.05 for s in symbols])
        cov_mat = np.diag(stds)

    # Portfolio stats (for reference)
    w_arr = np.array([weights[s] for s in symbols])
    port_mean = sum(weights[s] * ret_series[s].mean() for s in symbols)
    port_std = float(np.sqrt(w_arr @ cov_mat @ w_arr))

    # SPY stats
    spy_df = _load_history("SPY")
    if spy_df.empty or len(spy_df) < 12:
        spy_mean, spy_std = 0.008, 0.040
    else:
        spy_rets = spy_df["Close"].pct_change().dropna()
        spy_mean = float(spy_rets.mean())
        spy_std = float(spy_rets.std())

    spy_start = backtest.get("final_spy", start_value) if not backtest.get("error") else start_value

    # Date range
    today = datetime.date.today()
    future_dates = []
    d = today
    for _ in range(MC_MONTHS + 1):
        future_dates.append(d.strftime("%Y-%m-%d"))
        m = d.month + 1
        y = d.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        d = d.replace(year=y, month=m, day=min(d.day, 28))

    rng = np.random.default_rng(seed=42)

    def _simulate_multivariate(start: float, mu: float, cov: np.ndarray, w: np.ndarray) -> np.ndarray:
        n_assets = len(w)
        paths = np.empty((MC_PATHS, MC_MONTHS + 1))
        paths[:, 0] = start

        # Cholesky for correlated shocks — fall back to diagonal if matrix is not PSD
        try:
            L = np.linalg.cholesky(cov)
        except np.linalg.LinAlgError:
            L = np.diag(np.sqrt(np.maximum(np.diag(cov), 0.0)))

        for t in range(1, MC_MONTHS + 1):
            z = rng.normal(0.0, 1.0, size=(MC_PATHS, n_assets))
            correlated_returns = z @ L.T
            # geometric returns
            growth = np.exp(mu + correlated_returns)
            asset_paths = paths[:, t-1][:, np.newaxis] * growth
            # portfolio value = weighted sum
            paths[:, t] = np.dot(asset_paths, w)

        return paths

    # Drift correction
    port_geo_mean = port_mean - (port_std ** 2) / 2
    spy_geo_mean  = spy_mean - (spy_std ** 2) / 2

    # Portfolio paths with full correlation
    port_paths = _simulate_multivariate(start_value, port_geo_mean, cov_mat, w_arr)

    # SPY (independent)
    def _simulate(start: float, mu_geo: float, std: float) -> np.ndarray:
        paths = np.empty((MC_PATHS, MC_MONTHS + 1))
        paths[:, 0] = start
        z = rng.normal(0.0, 1.0, size=(MC_PATHS, MC_MONTHS))
        for t in range(1, MC_MONTHS + 1):
            growth = np.exp(mu_geo + std * z[:, t - 1])
            paths[:, t] = paths[:, t - 1] * growth
        return paths

    spy_paths = _simulate(spy_start, spy_geo_mean, spy_std)

    def _percentile_paths(paths: np.ndarray, pct: int) -> list[float]:
        return [round(float(fm.percentile(paths[:, t], pct) or 0.0), 2)
                for t in range(MC_MONTHS + 1)]

    return {
        "dates":       future_dates,
        "p10":         _percentile_paths(port_paths, 10),
        "p50":         _percentile_paths(port_paths, 50),
        "p90":         _percentile_paths(port_paths, 90),
        "spy_p10":     _percentile_paths(spy_paths, 10),
        "spy_p50":     _percentile_paths(spy_paths, 50),
        "spy_p90":     _percentile_paths(spy_paths, 90),
        "start_value": round(start_value, 2),
        "error":       None,
    }
# ══════════════════════════════════════════════════════════════════════════════
# Full simulation (backtest + Monte Carlo)
# ══════════════════════════════════════════════════════════════════════════════

def analyze_weak_links(portfolio: dict, backtest: dict | None = None) -> dict:
    """
    Identify which holdings dragged portfolio performance below SPY over 10 years.

    Two complementary lenses:

    1. Individual CAGR vs SPY  ─────────────────────────────────────────────────
       Each stock's own annualised return from the backtest start date, compared
       directly to SPY's CAGR over the same period.
       drag_bps = (stock_cagr − spy_cagr) × weight × 100   (basis points)
       Negative drag_bps = underperformance proportional to portfolio weight.

    2. Counterfactual swap  ────────────────────────────────────────────────────
       For each holding, ask: "If I had replaced only THIS stock with SPY,
       how would the portfolio have done?"
       swap_delta_pct = counterfactual_total_return − actual_total_return
       Positive swap_delta_pct means swapping this stock for SPY would have
       *improved* returns — i.e. this stock was a drag.

    Both lenses agree when a stock is truly the weak link. When they diverge,
    it is usually because a small-weight stock had a catastrophic individual
    return (lens 1 flags it) but its low weight limited the portfolio impact
    (lens 2 shows it barely mattered).

    Args:
        portfolio:  portfolio dict (from load_portfolio).
        backtest:   result of run_backtest(); if None, runs it internally.

    Returns dict:
        {
          "spy_cagr":    float,          # SPY CAGR over the period
          "port_cagr":   float,          # actual portfolio CAGR
          "gap_cagr":    float,          # port_cagr − spy_cagr  (negative = underperformed)
          "holdings": {
            SYM: {
              "weight":           float,  # $ weight at entry (0-1)
              "stock_cagr":       float,  # annualised return of this stock alone
              "spy_cagr":         float,  # same SPY CAGR for reference
              "cagr_vs_spy":      float,  # stock_cagr − spy_cagr
              "drag_bps":         float,  # weighted drag in basis points
              "swap_delta_pct":   float,  # total-return improvement if swapped for SPY
              "verdict":          str,    # "weak link" | "neutral" | "contributor"
            },
          },
          "ranking":  [SYM, ...],        # worst to best by drag_bps
          "weakest":  SYM | None,        # single biggest drag (by swap_delta_pct)
          "error":    str | None,
        }
    """
    holdings = portfolio.get("holdings", {})
    if not holdings:
        return {"error": "Portfolio is empty", "holdings": {}, "ranking": [], "weakest": None}

    # ── Run backtest if not supplied ──────────────────────────────────────────
    if backtest is None or backtest.get("error"):
        backtest = run_backtest(portfolio)
    if backtest.get("error"):
        return {"error": backtest["error"], "holdings": {}, "ranking": [], "weakest": None}

    symbols  = list(holdings.keys())
    available = [s for s in symbols if s in backtest.get("holdings_detail", {})]
    if not available:
        return {"error": "No holdings detail in backtest", "holdings": {}, "ranking": [], "weakest": None}

    port_cagr = backtest["cagr"]
    spy_cagr  = backtest["spy_cagr"]
    gap_cagr  = round(port_cagr - spy_cagr, 3)

    # ── Rebuild price matrices from history for counterfactual swaps ──────────
    histories: dict[str, pd.DataFrame] = {}
    for sym in available + ["SPY"]:
        h = _load_history(sym)
        if not h.empty:
            histories[sym] = h

    # We need a wide aligned frame exactly as in run_backtest
    to_align = {s: histories[s] for s in available + ["SPY"] if s in histories}
    wide = _align_histories(to_align)
    if wide.empty or len(wide) < 6:
        return {"error": "Insufficient price history for weak-link analysis",
                "holdings": {}, "ranking": [], "weakest": None}

    entry_row  = wide.iloc[0]
    exit_row   = wide.iloc[-1]
    n_months   = len(wide)
    n_years    = n_months / 12

    # ── Entry values & weights ────────────────────────────────────────────────
    port_created = portfolio.get("created", "2000-01-01")[:10]
    splits_by_sym: dict[str, list[dict]] = {}
    for sym in available:
        h     = holdings[sym]
        since = h.get("added_date") or port_created
        splits_by_sym[sym] = _splits_since(sym, since)

    entry_date = entry_row["Date"]
    entry_values: dict[str, float] = {}
    for sym in available:
        if sym not in wide.columns:
            continue
        factor = _split_factor_at(splits_by_sym[sym], entry_date)
        entry_values[sym] = holdings[sym]["shares"] * factor * float(entry_row[sym])

    total_entry = sum(entry_values.values())
    if total_entry <= 0:
        return {"error": "Zero portfolio entry value", "holdings": {}, "ranking": [], "weakest": None}

    weights = {sym: entry_values[sym] / total_entry for sym in entry_values}

    # ── Actual portfolio final value (replicated, split-adjusted) ────────────
    exit_date = exit_row["Date"]
    def _port_value_at_exit(exclude_sym: str | None = None,
                            replace_with_spy: bool = False) -> float:
        """
        Compute final portfolio value.
        If exclude_sym is set and replace_with_spy=True, that holding's
        entry $ are invested in SPY instead.
        """
        spy_price_entry = float(entry_row["SPY"])
        spy_price_exit  = float(exit_row["SPY"])

        total = 0.0
        for sym in available:
            if sym not in wide.columns:
                continue
            ev = entry_values[sym]
            if sym == exclude_sym and replace_with_spy:
                # Replace this holding with equivalent $ in SPY
                spy_shares_equiv = ev / spy_price_entry if spy_price_entry > 0 else 0
                total += spy_shares_equiv * spy_price_exit
            else:
                factor     = _split_factor_at(splits_by_sym[sym], exit_date)
                adj_shares = holdings[sym]["shares"] * factor
                total     += adj_shares * float(exit_row[sym])
        return total

    actual_final = _port_value_at_exit()
    actual_total_return = (actual_final / total_entry - 1) * 100 if total_entry > 0 else 0.0

    # ── Per-holding analysis ──────────────────────────────────────────────────
    result_holdings: dict[str, dict] = {}

    for sym in available:
        if sym not in wide.columns:
            continue

        # Individual stock CAGR over the aligned backtest window
        ep = float(entry_row[sym])
        cp = float(exit_row[sym])
        stock_total_return = (cp / ep - 1) if ep > 0 else 0.0
        stock_cagr_raw = fm.cagr(1.0, 1.0 + stock_total_return, n_years)
        stock_cagr = stock_cagr_raw * 100 if stock_cagr_raw is not None else 0.0

        cagr_vs_spy = stock_cagr - spy_cagr
        # Weighted drag: how many bps this stock cost relative to SPY
        drag_bps = cagr_vs_spy * weights[sym] * 100

        # Counterfactual: replace only this stock with SPY
        counterfactual_final = _port_value_at_exit(exclude_sym=sym, replace_with_spy=True)
        counterfactual_return = (counterfactual_final / total_entry - 1) * 100 if total_entry > 0 else 0.0
        swap_delta_pct = round(counterfactual_return - actual_total_return, 2)

        # Verdict thresholds
        if drag_bps < -30 or swap_delta_pct > 2.0:
            verdict = "weak link"
        elif drag_bps > 30 or swap_delta_pct < -2.0:
            verdict = "contributor"
        else:
            verdict = "neutral"

        result_holdings[sym] = {
            "weight":         round(weights[sym] * 100, 1),   # % of portfolio
            "stock_cagr":     round(stock_cagr, 2),
            "spy_cagr":       round(spy_cagr, 2),
            "cagr_vs_spy":    round(cagr_vs_spy, 2),
            "drag_bps":       round(drag_bps, 1),
            "swap_delta_pct": swap_delta_pct,
            "verdict":        verdict,
        }

    # ── Ranking: worst drag first ─────────────────────────────────────────────
    ranking = sorted(result_holdings.keys(),
                     key=lambda s: result_holdings[s]["drag_bps"])

    # Weakest = largest positive swap_delta (most improved if swapped for SPY)
    weakest = max(result_holdings, key=lambda s: result_holdings[s]["swap_delta_pct"],
                  default=None)
    if weakest and result_holdings[weakest]["swap_delta_pct"] <= 0:
        weakest = None  # every stock beat SPY — no weak link

    return {
        "spy_cagr":   round(spy_cagr, 2),
        "port_cagr":  round(port_cagr, 2),
        "gap_cagr":   gap_cagr,
        "n_years":    round(n_years, 1),
        "holdings":   result_holdings,
        "ranking":    ranking,
        "weakest":    weakest,
        "error":      None,
    }


def run_simulation(user_id: str, portfolio_name: str) -> dict:
    p = load_portfolio(user_id, portfolio_name)
    if p is None:
        return {"error": f'Portfolio "{portfolio_name}" not found'}

    cache_key = _simulation_key(user_id, portfolio_name)
    cached = cache.read("port_sim", cache_key)
    if cached:
        return cached
    cached = _read_cache_if_safe("port_sim", _legacy_simulation_key(user_id, portfolio_name))
    if cached:
        return cached

    bt = run_backtest(p)
    mc = run_montecarlo(p, bt)

    result = {
        "portfolio_name": portfolio_name,
        "backtest":       bt,
        "montecarlo":     mc,
        "holdings":       p["holdings"],
    }

    _write_cache_or_raise("port_sim", cache_key, result)
    return result


def invalidate_simulation_cache(user_id: str, portfolio_name: str) -> None:
    _clear_cache_if_safe("port_sim", _simulation_key(user_id, portfolio_name))
    _clear_cache_if_safe("port_sim", _legacy_simulation_key(user_id, portfolio_name))

def delete_all_user_data(user_id: str) -> dict:
    """
    Right-to-erasure (GDPR/CCPA): cascading delete of every piece of data
    this app stores under `user_id` — all portfolios, their simulation
    caches, and the portfolio index.

    sec_facts/hist/analysis caches are ticker-keyed, deterministic public
    market data (not user-owned) and are intentionally NOT deleted.
    """
    names = list_portfolios(user_id)
    for name in names:
        invalidate_simulation_cache(user_id, name)
        delete_portfolio(user_id, name)
    _clear_cache_if_safe("portfolio", _portfolio_index_key(user_id))
    _clear_cache_if_safe("portfolio", _legacy_index_key(user_id))
    return {"user_id": user_id, "portfolios_deleted": names, "deleted": True}
# ══════════════════════════════════════════════════════════════════════════════
# Multi-Portfolio Comparison (PROJECT_MAP.md — Portfolio Page Refactor)
# ══════════════════════════════════════════════════════════════════════════════

def _weak_link_score(portfolio: dict, backtest: dict) -> float:
    """
    0-100 score where 100 = no weak-link holdings.
    Reuses analyze_weak_links() without modifying it.
    """
    wl = analyze_weak_links(portfolio, backtest)
    if wl.get("error"):
        return 50.0
    holdings = wl.get("holdings", {})
    if not holdings:
        return 50.0
    n_weak = sum(1 for h in holdings.values() if h["verdict"] == "weak link")
    return round((1 - n_weak / len(holdings)) * 100, 2)


def compare_portfolios(user_id: str, portfolio_a_name: str, portfolio_b_name: str) -> dict:
    """
    Compare two portfolios for the Portfolio Page comparison view.

    Reuses run_simulation() (cached backtest + Monte Carlo) and
    analyze_weak_links() for both portfolios — does not re-implement or
    alter any existing simulation logic.

    score = (cagr * 0.40) + (alpha_vs_spy * 0.25)
          + (normalized_final_value * 0.15) + (normalized_p50 * 0.15)
          + (weak_link_score * 0.05)

    Returns:
      {
        "winner": str | None,        # None if scores are nearly identical
        "score_a": float,
        "score_b": float,
        "reasons": [str, ...],
        "portfolio_a": {...},         # run_simulation() result for A
        "portfolio_b": {...},         # run_simulation() result for B
        "error": str | None,
      }
    """
    sim_a = run_simulation(user_id, portfolio_a_name)
    sim_b = run_simulation(user_id, portfolio_b_name)

    if sim_a.get("error"):
        return {"error": sim_a["error"]}
    if sim_b.get("error"):
        return {"error": sim_b["error"]}

    bt_a, mc_a = sim_a["backtest"], sim_a["montecarlo"]
    bt_b, mc_b = sim_b["backtest"], sim_b["montecarlo"]

    if bt_a.get("error") or bt_b.get("error"):
        return {"error": "Backtest unavailable for one or both portfolios"}

    cagr_a, cagr_b = bt_a["cagr"], bt_b["cagr"]
    alpha_a = cagr_a - bt_a["spy_cagr"]
    alpha_b = cagr_b - bt_b["spy_cagr"]

    final_a, final_b = bt_a["final_value"], bt_b["final_value"]
    max_final = max(final_a, final_b, 1e-9)
    norm_final_a = final_a / max_final * 100
    norm_final_b = final_b / max_final * 100

    p50_a = mc_a["p50"][-1] if not mc_a.get("error") and mc_a.get("p50") else None
    p50_b = mc_b["p50"][-1] if not mc_b.get("error") and mc_b.get("p50") else None
    if p50_a is not None and p50_b is not None:
        max_p50 = max(p50_a, p50_b, 1e-9)
        norm_p50_a = p50_a / max_p50 * 100
        norm_p50_b = p50_b / max_p50 * 100
    else:
        norm_p50_a = norm_p50_b = 50.0

    p_a = load_portfolio(user_id, portfolio_a_name)
    p_b = load_portfolio(user_id, portfolio_b_name)
    wl_score_a = _weak_link_score(p_a, bt_a) if p_a else 50.0
    wl_score_b = _weak_link_score(p_b, bt_b) if p_b else 50.0

    def _composite(cagr, alpha, norm_final, norm_p50, wl_score):
        return (
            cagr * 0.40
            + alpha * 0.25
            + norm_final * 0.15
            + norm_p50 * 0.15
            + wl_score * 0.05
        )

    score_a = _composite(cagr_a, alpha_a, norm_final_a, norm_p50_a, wl_score_a)
    score_b = _composite(cagr_b, alpha_b, norm_final_b, norm_p50_b, wl_score_b)

    SCORE_TIE_THRESHOLD = 1.0
    score_diff = score_a - score_b

    if abs(score_diff) < SCORE_TIE_THRESHOLD:
        winner = None
    elif score_diff > 0:
        winner = portfolio_a_name
    else:
        winner = portfolio_b_name

    reasons: list[str] = []
    if winner is not None:
        winner_is_a = winner == portfolio_a_name
        w_cagr, l_cagr = (cagr_a, cagr_b) if winner_is_a else (cagr_b, cagr_a)
        w_alpha, l_alpha = (alpha_a, alpha_b) if winner_is_a else (alpha_b, alpha_a)
        w_final, l_final = (final_a, final_b) if winner_is_a else (final_b, final_a)
        w_p50, l_p50 = (p50_a, p50_b) if winner_is_a else (p50_b, p50_a)
        w_wl, l_wl = (wl_score_a, wl_score_b) if winner_is_a else (wl_score_b, wl_score_a)

        if w_cagr > l_cagr:
            reasons.append("Higher CAGR")
        if w_alpha > l_alpha:
            reasons.append("Better alpha vs SPY")
        if w_final > l_final:
            reasons.append("Higher final portfolio value")
        if w_p50 is not None and l_p50 is not None and w_p50 > l_p50:
            reasons.append("Higher projected median value")
        if w_wl > l_wl:
            reasons.append("Fewer weak-link holdings")

        if not reasons:
            reasons.append("Higher overall composite score")
    else:
        reasons.append("Both portfolios perform similarly.")

    return {
        "winner":      winner,
        "score_a":     round(score_a, 2),
        "score_b":     round(score_b, 2),
        "reasons":     reasons,
        "portfolio_a": sim_a,
        "portfolio_b": sim_b,
        "error":       None,
    }
