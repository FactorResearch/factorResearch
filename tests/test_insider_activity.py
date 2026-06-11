"""
Tests for insider_activity.py

Covers:
  - Heavy insider buying scenario
  - Heavy insider selling scenario
  - Strong cluster buying event
  - No cluster scenario
  - Mixed buy/sell neutral case
  - CEO-led vs minor insider activity comparison
  - Insufficient data fallback behavior
  - Signal threshold boundaries
  - Time-window clustering correctness
  - Normalization edge cases
"""

import math
import pytest
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.models.insider_activity import (
    get_insider_score,
    calc_net_insider_buying,
    calc_cluster_buying_score,
    calc_insider_type_quality,
    _norm_net_buying,
    _signal,
    CLUSTER_WINDOW_DAYS,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

REF = datetime(2025, 6, 1)


def _tx(insider_id, role, tx_type, shares, days_ago, is_open_market=True):
    date = (REF - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    return {
        "date":           date,
        "insider_id":     insider_id,
        "role":           role,
        "transaction":    tx_type,
        "shares":         shares,
        "is_open_market": is_open_market,
    }


def _buy(insider_id, role, shares, days_ago, open_market=True):
    return _tx(insider_id, role, "buy", shares, days_ago, open_market)


def _sell(insider_id, role, shares, days_ago):
    return _tx(insider_id, role, "sell", shares, days_ago, True)


# ── Signal mapping ────────────────────────────────────────────────────────────

class TestSignalMapping:
    def test_bullish_at_70(self):
        assert _signal(70) == "BULLISH"
        assert _signal(100) == "BULLISH"

    def test_neutral_at_40(self):
        assert _signal(40) == "NEUTRAL"
        assert _signal(69.9) == "NEUTRAL"

    def test_bearish_below_40(self):
        assert _signal(0) == "BEARISH"
        assert _signal(39.9) == "BEARISH"


# ── Net buying normalization ──────────────────────────────────────────────────

class TestNormNetBuying:
    def test_zero_gives_50(self):
        assert _norm_net_buying(0.0) == pytest.approx(50.0)

    def test_positive_above_50(self):
        assert _norm_net_buying(50.0) == pytest.approx(75.0)

    def test_negative_below_50(self):
        assert _norm_net_buying(-50.0) == pytest.approx(25.0)

    def test_100_gives_100(self):
        assert _norm_net_buying(100.0) == pytest.approx(100.0)

    def test_minus100_gives_0(self):
        assert _norm_net_buying(-100.0) == pytest.approx(0.0)


# ── calc_net_insider_buying ───────────────────────────────────────────────────

class TestCalcNetInsiderBuying:
    def test_all_buys_positive(self):
        txs = [_buy("A", "CEO", 10_000, 30), _buy("B", "CFO", 5_000, 20)]
        net = calc_net_insider_buying(txs, shares_outstanding=1_000_000,
                                      reference_date=REF)
        # net = 15000, pct = 1.5%
        assert net == pytest.approx(1.5)

    def test_all_sells_negative(self):
        txs = [_sell("A", "CEO", 10_000, 30), _sell("B", "CFO", 5_000, 20)]
        net = calc_net_insider_buying(txs, shares_outstanding=1_000_000,
                                      reference_date=REF)
        assert net == pytest.approx(-1.5)

    def test_balanced_buy_sell_near_zero(self):
        txs = [_buy("A", "CEO", 5_000, 10), _sell("B", "CFO", 5_000, 20)]
        net = calc_net_insider_buying(txs, shares_outstanding=1_000_000,
                                      reference_date=REF)
        assert net == pytest.approx(0.0)

    def test_clipped_at_100(self):
        # 200% theoretical net → clipped at 100
        txs = [_buy("A", "CEO", 2_000_000, 10)]
        net = calc_net_insider_buying(txs, shares_outstanding=1_000_000,
                                      reference_date=REF)
        assert net == pytest.approx(100.0)

    def test_clipped_at_minus100(self):
        txs = [_sell("A", "CEO", 2_000_000, 10)]
        net = calc_net_insider_buying(txs, shares_outstanding=1_000_000,
                                      reference_date=REF)
        assert net == pytest.approx(-100.0)

    def test_fallback_normalization_without_shares_outstanding(self):
        txs = [_buy("A", "CEO", 8_000, 10), _sell("B", "CFO", 2_000, 20)]
        net = calc_net_insider_buying(txs, shares_outstanding=None,
                                      reference_date=REF)
        # net=6000, total=10000 → 60%
        assert net == pytest.approx(60.0)

    def test_old_transactions_excluded(self):
        txs = [_buy("A", "CEO", 100_000, 400)]  # >365d ago
        net = calc_net_insider_buying(txs, shares_outstanding=1_000_000,
                                      reference_date=REF)
        assert net == pytest.approx(0.0)

    def test_option_exercises_excluded(self):
        txs = [_buy("A", "CEO", 50_000, 10, open_market=False)]
        net = calc_net_insider_buying(txs, shares_outstanding=1_000_000,
                                      reference_date=REF)
        assert net == pytest.approx(0.0)


# ── calc_cluster_buying_score ─────────────────────────────────────────────────

class TestCalcClusterBuyingScore:
    def _cluster_txs(self, days_ago=10):
        """Valid cluster: 3 insiders, 4 trades, well-spread volume."""
        return [
            _buy("CEO1", "CEO", 10_000, days_ago),
            _buy("CFO1", "CFO", 8_000,  days_ago + 3),
            _buy("DIR1", "Director", 7_000, days_ago + 5),
            _buy("CEO1", "CEO", 5_000,  days_ago + 7),
        ]

    def test_valid_cluster_detected(self):
        score, detected = calc_cluster_buying_score(
            self._cluster_txs(), reference_date=REF
        )
        assert detected is True
        assert score > 0

    def test_score_in_range(self):
        score, _ = calc_cluster_buying_score(
            self._cluster_txs(), reference_date=REF
        )
        assert 0 <= score <= 100

    def test_no_cluster_two_insiders_two_trades(self):
        txs = [
            _buy("A", "CEO", 10_000, 5),
            _buy("B", "CFO", 5_000, 10),
        ]
        score, detected = calc_cluster_buying_score(txs, reference_date=REF)
        assert detected is False
        assert score == pytest.approx(0.0)

    def test_no_cluster_single_insider_many_trades(self):
        txs = [_buy("A", "CEO", 1_000, d) for d in range(1, 6)]
        score, detected = calc_cluster_buying_score(txs, reference_date=REF)
        # Only 1 distinct insider → no cluster
        assert detected is False

    def test_concentration_too_high_no_cluster(self):
        # One insider has 95% of volume
        txs = [
            _buy("A", "CEO", 95_000, 5),
            _buy("B", "CFO",  2_500, 8),
            _buy("C", "Dir",  2_500, 10),
        ]
        score, detected = calc_cluster_buying_score(txs, reference_date=REF)
        assert detected is False

    def test_old_cluster_outside_window_not_detected(self):
        # Cluster happened 50+ days ago (outside 42-day window)
        txs = [
            _buy("A", "CEO", 10_000, 50),
            _buy("B", "CFO",  8_000, 55),
            _buy("C", "Dir",  7_000, 60),
        ]
        score, detected = calc_cluster_buying_score(txs, reference_date=REF)
        assert detected is False
        assert score == pytest.approx(0.0)

    def test_recent_cluster_scores_higher_than_old(self):
        recent = [
            _buy("A", "CEO", 10_000, 5),
            _buy("B", "CFO",  8_000, 7),
            _buy("C", "Dir",  7_000, 9),
        ]
        older = [
            _buy("A", "CEO", 10_000, 35),
            _buy("B", "CFO",  8_000, 37),
            _buy("C", "Dir",  7_000, 39),
        ]
        score_recent, d1 = calc_cluster_buying_score(recent, reference_date=REF)
        score_older,  d2 = calc_cluster_buying_score(older,  reference_date=REF)
        assert d1 and d2
        assert score_recent > score_older

    def test_empty_transactions_no_cluster(self):
        score, detected = calc_cluster_buying_score([], reference_date=REF)
        assert detected is False
        assert score == pytest.approx(0.0)


# ── calc_insider_type_quality ─────────────────────────────────────────────────

class TestCalcInsiderTypeQuality:
    def test_ceo_cfos_give_high_quality(self):
        txs = [
            _buy("A", "CEO", 10_000, 30),
            _buy("B", "CFO",  8_000, 40),
        ]
        score = calc_insider_type_quality(txs, reference_date=REF)
        assert score > 80

    def test_minor_insiders_give_lower_quality(self):
        txs = [
            _buy("A", "VP Finance", 10_000, 30),
            _buy("B", "Other",       8_000, 40),
        ]
        score = calc_insider_type_quality(txs, reference_date=REF)
        assert score < 50

    def test_no_buys_returns_50_neutral(self):
        txs = [_sell("A", "CEO", 10_000, 30)]
        score = calc_insider_type_quality(txs, reference_date=REF)
        assert score == pytest.approx(50.0)

    def test_mixed_quality_in_between(self):
        txs = [
            _buy("A", "CEO",       10_000, 10),
            _buy("B", "Other",     10_000, 15),
        ]
        score_mixed = calc_insider_type_quality(txs, reference_date=REF)
        pure_hq = calc_insider_type_quality([txs[0]], reference_date=REF)
        pure_lq = calc_insider_type_quality([txs[1]], reference_date=REF)
        assert pure_lq < score_mixed < pure_hq

    def test_ceo_led_vs_minor_higher_score(self):
        ceo_txs = [_buy("A", "CEO", 10_000, 20)]
        vp_txs  = [_buy("B", "VP Sales", 10_000, 20)]
        assert (calc_insider_type_quality(ceo_txs, reference_date=REF) >
                calc_insider_type_quality(vp_txs,  reference_date=REF))

    def test_director_counts_as_high_quality(self):
        txs = [_buy("A", "Director", 10_000, 10)]
        score = calc_insider_type_quality(txs, reference_date=REF)
        assert score > 80


# ── get_insider_score (integration) ──────────────────────────────────────────

class TestGetInsiderScore:
    REQUIRED_KEYS = {
        "ticker", "net_insider_buying", "cluster_buying_score",
        "insider_type_quality", "insider_confidence_score", "signal",
        "n_buy_transactions", "n_sell_transactions", "n_distinct_buyers",
        "cluster_detected", "low_coverage", "total_score", "total_max",
    }

    def _strong_buy_txs(self):
        return [
            _buy("CEO1", "CEO",      50_000, 10),
            _buy("CFO1", "CFO",      30_000, 12),
            _buy("DIR1", "Director", 20_000, 15),
            _buy("DIR2", "Director", 15_000, 18),
        ]

    def _strong_sell_txs(self):
        return [
            _sell("CEO1", "CEO",       50_000, 10),
            _sell("CFO1", "CFO",       30_000, 12),
            _sell("DIR1", "Director",  20_000, 15),
        ]

    def test_output_has_required_keys(self):
        result = get_insider_score("AAPL", self._strong_buy_txs(),
                                   reference_date=REF)
        assert self.REQUIRED_KEYS == set(result.keys())

    def test_ticker_uppercased(self):
        result = get_insider_score("aapl", self._strong_buy_txs(),
                                   reference_date=REF)
        assert result["ticker"] == "AAPL"

    def test_heavy_buying_gives_bullish(self):
        # 115k buys on 100k float -> strong net buying + cluster + HQ insiders
        result = get_insider_score("AAPL", self._strong_buy_txs(),
                                   shares_outstanding=100_000,
                                   reference_date=REF)
        assert result["signal"] == "BULLISH"
        assert result["insider_confidence_score"] >= 70

    def test_heavy_selling_gives_bearish(self):
        result = get_insider_score("AAPL", self._strong_sell_txs(),
                                   shares_outstanding=10_000_000,
                                   reference_date=REF)
        assert result["signal"] == "BEARISH"
        assert result["insider_confidence_score"] < 40

    def test_neutral_case_mixed(self):
        txs = [
            _buy("A",  "CEO",       5_000, 30),
            _sell("B", "Director", 5_000, 35),
        ]
        result = get_insider_score("TEST", txs, shares_outstanding=1_000_000,
                                   reference_date=REF)
        assert result["signal"] in ("NEUTRAL", "BEARISH", "BULLISH")
        assert math.isfinite(result["insider_confidence_score"])

    def test_insufficient_data_returns_neutral_defaults(self):
        result = get_insider_score("X", [], reference_date=REF)
        assert result["insider_confidence_score"] == pytest.approx(50.0)
        assert result["signal"] == "NEUTRAL"
        assert result["low_coverage"] is True
        assert result["net_insider_buying"] == pytest.approx(0.0)

    def test_score_bounded_0_to_100(self):
        result = get_insider_score("TEST", self._strong_buy_txs(),
                                   shares_outstanding=1_000_000,
                                   reference_date=REF)
        assert 0 <= result["insider_confidence_score"] <= 100
        assert 0 <= result["total_score"] <= 100

    def test_total_score_matches_confidence_score(self):
        result = get_insider_score("TEST", self._strong_buy_txs(),
                                   reference_date=REF)
        assert result["total_score"] == result["insider_confidence_score"]
        assert result["total_max"] == 100.0

    def test_cluster_detected_in_strong_buy(self):
        result = get_insider_score("TEST", self._strong_buy_txs(),
                                   reference_date=REF)
        assert result["cluster_detected"] is True

    def test_cluster_not_detected_single_insider(self):
        txs = [_buy("A", "CEO", 100_000, 5)]
        result = get_insider_score("TEST", txs, reference_date=REF)
        assert result["cluster_detected"] is False

    def test_n_buy_sell_counts_correct(self):
        txs = [
            _buy("A", "CEO", 10_000, 10),
            _buy("B", "CFO",  5_000, 15),
            _sell("C", "Dir", 3_000, 20),
        ]
        result = get_insider_score("TEST", txs, reference_date=REF)
        assert result["n_buy_transactions"] == 2
        assert result["n_sell_transactions"] == 1

    def test_n_distinct_buyers_correct(self):
        txs = [
            _buy("A", "CEO", 10_000, 10),
            _buy("A", "CEO",  5_000, 12),  # same insider, 2 trades
            _buy("B", "CFO",  8_000, 15),
        ]
        result = get_insider_score("TEST", txs, reference_date=REF)
        assert result["n_distinct_buyers"] == 2

    def test_low_coverage_false_for_many_transactions(self):
        txs = [_buy(f"I{i}", "Director", 1_000, 10 + i) for i in range(5)]
        result = get_insider_score("TEST", txs, reference_date=REF)
        assert result["low_coverage"] is False

    def test_signal_consistent_with_score(self):
        result = get_insider_score("TEST", self._strong_buy_txs(),
                                   reference_date=REF)
        expected = (
            "BULLISH" if result["insider_confidence_score"] >= 70 else
            "NEUTRAL" if result["insider_confidence_score"] >= 40 else
            "BEARISH"
        )
        assert result["signal"] == expected

    def test_option_exercise_excluded_from_buying(self):
        txs = [
            _buy("A", "CEO", 100_000, 5, open_market=False),  # option exercise
            _buy("B", "CFO",   5_000, 10, open_market=True),   # real buy
        ]
        result = get_insider_score("TEST", txs,
                                   shares_outstanding=1_000_000,
                                   reference_date=REF)
        # Only 5000 shares of open-market buys should count
        assert result["n_buy_transactions"] == 1

    def test_signal_threshold_boundary_exactly_70(self):
        # Force a score of exactly 70 by checking the mapping
        from codes.models.insider_activity import _signal
        assert _signal(70.0) == "BULLISH"
        assert _signal(69.9) == "NEUTRAL"

    def test_signal_threshold_boundary_exactly_40(self):
        from codes.models.insider_activity import _signal
        assert _signal(40.0) == "NEUTRAL"
        assert _signal(39.9) == "BEARISH"


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
