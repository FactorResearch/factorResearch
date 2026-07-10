import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.engine import scorer
from codes.models.options_signal_engine import OptionsSignalEngine


def _hist(closes):
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="MS")
    return pd.DataFrame({"Date": dates, "Close": closes})


def test_issue_027_standard_and_enhanced_verdicts_avoid_legal_terms():
    prohibited = {"BUY", "SELL", "HOLD"}
    for thresholds in (scorer.VERDICTS, scorer.ENHANCED_VERDICTS):
        for _threshold, verdict, label, _description in thresholds:
            parts = set(verdict.replace("/", " ").replace("-", " ").upper().split())
            label_parts = set(label.replace("_", " ").replace("-", " ").upper().split())
            assert prohibited.isdisjoint(parts)
            assert prohibited.isdisjoint(label_parts)


def test_issue_027_options_signal_uses_safe_directional_labels():
    engine = OptionsSignalEngine(
        "TEST",
        price_hist=_hist([100, 104, 108, 113, 119, 126]),
        regime_result={"market_trend_score": 92, "volatility_percentile": 15, "vol_20d": 10, "vol_60d": 20},
        current_price=126.0,
    )

    signal = engine.get_options_signal()["signal"]

    assert signal == "HIGH_CONVICTION_CALL"
    assert all(term not in signal for term in ("BUY", "SELL", "HOLD"))
