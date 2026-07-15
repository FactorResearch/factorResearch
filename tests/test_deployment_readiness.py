import threading
from pathlib import Path

from codes.services import analysis_jobs


ROOT = Path(__file__).resolve().parents[1]


def test_release_preflight_runs_before_migration():
    command = (ROOT / "scripts" / "release-migrate.sh").read_text()
    assert command.index("check-production-config.py") < command.index("codes.data.migrate")
    assert "set -euo pipefail" in command
    assert "release: ./scripts/release-migrate.sh" in (ROOT / "Procfile").read_text()


def test_analysis_worker_honors_stop_event_without_consuming(monkeypatch):
    stop = threading.Event()
    stop.set()
    monkeypatch.setattr(analysis_jobs, "get_redis", lambda: (_ for _ in ()).throw(AssertionError("worker polled after stop")))
    analysis_jobs.work_forever(stop)


def test_release_runbook_has_numeric_rollback_criteria():
    runbook = (ROOT / "artifacts" / "production-proof" / "09-deployment" / "release-runbook.md").read_text()
    for requirement in ("5%", "25%", "error ratio", "p95", "previous compatible artifact"):
        assert requirement in runbook
