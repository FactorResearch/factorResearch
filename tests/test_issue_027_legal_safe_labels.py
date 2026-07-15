import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.engine import scorer


def test_issue_027_standard_and_enhanced_verdicts_avoid_legal_terms():
    prohibited = {"BUY", "SELL", "HOLD"}
    for thresholds in (scorer.VERDICTS, scorer.ENHANCED_VERDICTS):
        for _threshold, verdict, label, _description in thresholds:
            parts = set(verdict.replace("/", " ").replace("-", " ").upper().split())
            label_parts = set(label.replace("_", " ").replace("-", " ").upper().split())
            assert prohibited.isdisjoint(parts)
            assert prohibited.isdisjoint(label_parts)
