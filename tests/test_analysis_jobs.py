import threading
from unittest.mock import Mock, call

from codes.services import analysis_jobs


def test_local_job_fallback_dispatches_secondary_analysis(monkeypatch):
    completed = threading.Event()
    monkeypatch.setattr(analysis_jobs, "get_redis", lambda: None)
    monkeypatch.setattr(analysis_jobs, "_dispatch", lambda job: completed.set())

    analysis_jobs.enqueue({"type": "secondary-analysis", "symbol": "AAPL"})

    assert completed.wait(timeout=1)


def test_existing_stock_backfill_queues_each_unique_symbol(monkeypatch):
    enqueue = Mock()
    monkeypatch.setattr(analysis_jobs, "enqueue", enqueue)

    count = analysis_jobs.enqueue_existing_stock_backfill(["msft", "AAPL", "MSFT", ""])

    assert count == 2
    assert enqueue.call_args_list == [
        call({"type": "refresh-analysis", "symbol": "AAPL"}),
        call({"type": "refresh-analysis", "symbol": "MSFT"}),
    ]
