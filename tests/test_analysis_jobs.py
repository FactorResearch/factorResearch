import json
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


def test_consumer_acknowledges_only_after_success(monkeypatch):
    raw = json.dumps({"type": "refresh-analysis", "symbol": "AAPL"})
    redis = Mock()
    redis.brpoplpush.return_value = raw
    dispatch = Mock()
    monkeypatch.setattr(analysis_jobs, "_dispatch", dispatch)
    assert analysis_jobs.consume_one(redis)
    dispatch.assert_called_once()
    redis.lrem.assert_called_once_with(analysis_jobs._PROCESSING_QUEUE, 1, raw)


def test_consumer_retries_failed_inflight_job(monkeypatch):
    raw = json.dumps({"type": "refresh-analysis", "symbol": "AAPL"})
    redis = Mock()
    redis.brpoplpush.return_value = raw
    monkeypatch.setattr(analysis_jobs, "_dispatch", Mock(side_effect=RuntimeError("failed")))
    assert analysis_jobs.consume_one(redis)
    redis.lrem.assert_called_once_with(analysis_jobs._PROCESSING_QUEUE, 1, raw)
    retried = json.loads(redis.rpush.call_args.args[1])
    assert retried["attempts"] == 1


def test_worker_startup_recovers_unacknowledged_jobs():
    redis = Mock()
    redis.rpoplpush.side_effect = ["job-2", "job-1", None]
    assert analysis_jobs.recover_interrupted_jobs(redis) == 2
