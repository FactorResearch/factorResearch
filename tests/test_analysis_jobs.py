import threading

from codes.services import analysis_jobs


def test_local_job_fallback_dispatches_secondary_analysis(monkeypatch):
    completed = threading.Event()
    monkeypatch.setattr(analysis_jobs, "get_redis", lambda: None)
    monkeypatch.setattr(analysis_jobs, "_dispatch", lambda job: completed.set())

    analysis_jobs.enqueue({"type": "secondary-analysis", "symbol": "AAPL"})

    assert completed.wait(timeout=1)
