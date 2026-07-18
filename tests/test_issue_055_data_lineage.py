from datetime import UTC, datetime, timedelta

from codes.data import cache
from codes.services.data_lineage import FreshnessState, build_lineage, freshness_state


def test_freshness_states_distinguish_current_stale_expired_and_unknown() -> None:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    assert freshness_state(now.isoformat(), now=now, ttl_seconds=60) == FreshnessState.CURRENT
    assert freshness_state((now - timedelta(seconds=61)).isoformat(), now=now, ttl_seconds=60) == FreshnessState.STALE
    assert freshness_state((now - timedelta(seconds=121)).isoformat(), now=now, ttl_seconds=60) == FreshnessState.EXPIRED
    assert freshness_state(now.isoformat(), now=now, ttl_seconds=None) == FreshnessState.UNAVAILABLE
    assert freshness_state(None, now=now, ttl_seconds=60) == FreshnessState.UNAVAILABLE


def test_lineage_is_json_safe_and_preserves_source_timestamp() -> None:
    lineage = build_lineage(
        source="SEC EDGAR",
        acquired_at="2026-07-18T12:00:00+00:00",
        source_timestamp="2026-06-30",
        freshness_policy="filing-aware",
    )
    assert lineage["source"] == "SEC EDGAR"
    assert lineage["source_timestamp"] == "2026-06-30"
    assert lineage["freshness_state"] == "unavailable"


def test_cache_envelope_persists_lineage_without_changing_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    assert cache.write(
        "sec_facts",
        "aapl",
        {"revenue": 1},
        latest_filing="2026-06-30",
    )
    entry = cache.read_entry("sec_facts", "aapl")
    assert entry["data"] == {"revenue": 1}
    assert entry["lineage"]["source"] == "sec_facts"
    assert entry["lineage"]["source_timestamp"] == "2026-06-30"
    assert entry["lineage"]["freshness_policy"] == "filing-aware"
