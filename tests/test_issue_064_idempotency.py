"""Acceptance tests for ISSUE_064 idempotent commands and writes."""

from pathlib import Path

import pytest

from codes.services.idempotency import (
    IdempotencyConflict,
    IdempotencyService,
    InMemoryIdempotencyStore,
)


@pytest.fixture()
def isolated_cache(tmp_path, monkeypatch):
    from codes.data import cache

    monkeypatch.setenv("ENCRYPTION_KEY", "yi1myb0TPr6CavFrLrf1lgV6MChXb5VSNK4FDqFpdlw=")
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache._encryptor = None
    yield tmp_path
    cache._encryptor = None


def test_same_command_replays_original_outcome_without_second_side_effect() -> None:
    service = IdempotencyService(InMemoryIdempotencyStore())
    calls: list[int] = []

    def handler() -> dict[str, str]:
        calls.append(1)
        return {"created_id": "p-1"}

    first = service.execute(
        user_id="u1", key="cmd-1", operation="portfolio.create", payload={"name": "Core"}, handler=handler
    )
    second = service.execute(
        user_id="u1", key="cmd-1", operation="portfolio.create", payload={"name": "Core"}, handler=handler
    )
    assert first.response == second.response == {"created_id": "p-1"}
    assert first.replayed is False and second.replayed is True
    assert len(calls) == 1


def test_key_reuse_with_different_payload_is_rejected() -> None:
    service = IdempotencyService(InMemoryIdempotencyStore())
    service.execute(
        user_id="u1", key="cmd-1", operation="portfolio.create", payload={"name": "Core"}, handler=lambda: "one"
    )
    with pytest.raises(IdempotencyConflict):
        service.execute(
            user_id="u1", key="cmd-1", operation="portfolio.create", payload={"name": "Other"}, handler=lambda: "two"
        )


def test_portfolio_create_replays_same_record(isolated_cache, monkeypatch) -> None:
    from codes import portfolio

    monkeypatch.setattr(portfolio, "idempotency", IdempotencyService(InMemoryIdempotencyStore()))
    first = portfolio.create_portfolio("u1", "Core", idempotency_key="create-core")
    second = portfolio.create_portfolio("u1", "Core", idempotency_key="create-core")
    assert first["id"] == second["id"]
    assert portfolio.list_portfolios("u1") == ["Core"]


def test_keyed_job_submission_replays_job_id(monkeypatch) -> None:
    from codes.services import analysis_jobs

    service = IdempotencyService(InMemoryIdempotencyStore())
    monkeypatch.setattr(analysis_jobs, "idempotency", service)
    submitted: list[dict] = []
    monkeypatch.setattr(
        analysis_jobs,
        "_enqueue_once",
        lambda job: submitted.append(job) or {"job_id": "job-1", "status": "queued"},
    )
    job = {"type": "secondary-analysis", "symbol": "AAPL", "user_id": "u1", "idempotency_key": "job-key"}
    assert analysis_jobs.enqueue(job) == {"job_id": "job-1", "status": "queued"}
    replay = analysis_jobs.enqueue(job)
    assert replay == {"job_id": "job-1", "status": "queued"}
    assert len(submitted) == 1


def test_keyed_analysis_submission_replays_result(monkeypatch) -> None:
    from codes.services import stock_analysis

    service = IdempotencyService(InMemoryIdempotencyStore())
    monkeypatch.setattr(stock_analysis, "idempotency", service)
    calls: list[str] = []
    monkeypatch.setattr(stock_analysis, "_analyze_stock", lambda symbol, **_kwargs: calls.append(symbol) or {"symbol": symbol})
    first = stock_analysis.analyze_stock("AAPL", user_id="u1", idempotency_key="analysis-key")
    second = stock_analysis.analyze_stock("AAPL", user_id="u1", idempotency_key="analysis-key")
    assert first == second == {"symbol": "AAPL"}
    assert calls == ["AAPL"]


def test_idempotency_migration_is_additive_and_versioned() -> None:
    migration = Path("migrations/002_issue_064_idempotency_users.sql").read_text()
    assert "PRIMARY KEY (user_id, idempotency_key)" in migration
    assert "response_json" in migration
    assert "CREATE TABLE IF NOT EXISTS" in migration
