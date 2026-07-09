import os
import sys
import importlib.util
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_MODULE_PATH = Path(__file__).resolve().parents[1] / "codes" / "engine" / "market_fear.py"
_SPEC = importlib.util.spec_from_file_location("market_fear", _MODULE_PATH)
market_fear = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(market_fear)


def test_market_fear_uses_z_score_when_history_is_available():
    history = [1.0] * 80 + [3.0] * 80

    result = market_fear.analyze(20.0, 27.0, spread_history=history)

    assert result["error"] is None
    assert result["spread"] == 7.0
    assert result["z_score"] is not None
    assert result["regime"] == market_fear.EXTREME
    assert result["badge"] == "Extreme Market Fear"


def test_market_fear_falls_back_to_raw_spread_and_ratio():
    result = market_fear.analyze(22.0, 26.0)

    assert result["error"] is None
    assert result["spread"] == 4.0
    assert result["ratio"] == 1.182
    assert result["z_score"] is None
    assert result["regime"] == market_fear.ELEVATED


def test_market_fear_low_regime_requires_low_vix_and_tight_spread():
    result = market_fear.analyze(12.0, 12.8)

    assert result["regime"] == market_fear.VERY_LOW_FEAR
    assert result["market_fear_score"] == 10.0


def test_market_fear_missing_inputs_returns_error_without_exception():
    result = market_fear.analyze(None, 25.0)

    assert result["error"]
    assert result["regime"] is None
    assert result["market_fear_score"] is None
