from codes.services import analysis_snapshot_service as snapshots


def test_canonical_analytics_database_has_priority(monkeypatch):
    monkeypatch.setenv("DATABASE_ANALYTICS_URL", "postgresql://localhost/canonical")
    monkeypatch.setenv("ANALYTICS_DATABASE_URL", "postgresql://localhost/legacy")
    monkeypatch.setenv("DATABASE_MARKET_URL", "postgresql://localhost/market")
    assert snapshots._database_url().endswith("/canonical")
    assert snapshots._database_urls() == [
        "postgresql://localhost/canonical",
        "postgresql://localhost/legacy",
        "postgresql://localhost/market",
    ]


def test_duplicate_database_candidates_are_removed(monkeypatch):
    monkeypatch.setenv("DATABASE_ANALYTICS_URL", "postgresql://localhost/shared")
    monkeypatch.setenv("ANALYTICS_DATABASE_URL", "postgresql://localhost/shared")
    monkeypatch.delenv("FACTORRESEARCH_ANALYTICS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_MARKET_URL", "postgresql://localhost/market")
    assert snapshots._database_urls() == [
        "postgresql://localhost/shared",
        "postgresql://localhost/market",
    ]
