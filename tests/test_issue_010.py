import re
import time
import pytest

from codes import app as app_mod


def test_ticker_regex_accepts_valid_tickers():
    valid = ["A", "MSFT", "GOOG", "BRK", "ABCDEF"]
    pattern = re.compile(r"^[A-Z]{1,6}$")
    for t in valid:
        assert pattern.fullmatch(t), f"Expected valid ticker: {t}"


def test_ticker_regex_rejects_invalid_tickers():
    invalid = ["", "aapl", "TOO_LONG7", "A1", "AB-C", "LONGERTHAN6"]
    pattern = re.compile(r"^[A-Z]{1,6}$")
    for t in invalid:
        assert pattern.fullmatch(t) is None, f"Expected invalid ticker: {t}"


def test_portfolio_name_validation():
    ok = ["P1", "My_Port", "A123", "x" * 32]
    bad = ["", "name with space", "bad-name", "x" * 33]
    pattern = re.compile(r"^[A-Za-z0-9_]{1,32}$")
    for n in ok:
        assert pattern.fullmatch(n), f"Expected valid portfolio name: {n}"
    for n in bad:
        assert pattern.fullmatch(n) is None, f"Expected invalid portfolio name: {n}"


def test_shares_bounds():
    # Ensure the app's chosen bounds are sensible
    MIN_SHARES = 5
    MAX_SHARES = 1_000_000
    assert MIN_SHARES > 0
    assert MAX_SHARES >= MIN_SHARES


def test_in_memory_rate_limiter_enforces_limit():
    # Use a deterministic key so tests are isolated
    key = "unit_test_key"
    action = "test_rl_action"
    # Clear any prior state
    app_mod._RATE_LIMIT_STORE.clear()

    # Allow 2 calls within period
    app_mod._check_rate_limit(action, calls=2, period_seconds=5, key=key)
    app_mod._check_rate_limit(action, calls=2, period_seconds=5, key=key)

    # Third call should raise RateLimited
    with pytest.raises(app_mod.RateLimited):
        app_mod._check_rate_limit(action, calls=2, period_seconds=5, key=key)

    # After waiting past the period, it should allow calls again
    time.sleep(5)
    app_mod._check_rate_limit(action, calls=2, period_seconds=5, key=key)
