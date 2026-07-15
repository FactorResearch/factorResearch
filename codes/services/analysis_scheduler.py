"""Background refresh for shared context and configured popular symbols."""

import os
import signal
import threading
import time

from codes.core.config import is_production

_started = False
_lock = threading.Lock()
_stop_event = threading.Event()


def _enabled() -> bool:
    if os.environ.get("ANALYSIS_BACKGROUND_JOBS") != "1":
        return False
    return not is_production() or os.environ.get("PROCESS_ROLE") == "analysis-worker"


def _popular_symbols() -> list[str]:
    configured = [item.strip().upper() for item in os.environ.get("PRECOMPUTE_SYMBOLS", "").split(",") if item.strip()]
    if configured:
        return configured[: int(os.environ.get("PRECOMPUTE_LIMIT", "20"))]
    from codes.services import analysis_demand
    limit = int(os.environ.get("PRECOMPUTE_LIMIT", "20"))
    demanded = analysis_demand.popular(limit)
    if demanded:
        return demanded
    from codes.data import db
    return db.list_analysis_tickers()[:limit]


def run_maintenance_once() -> None:
    from codes.app_modules.analysis import (
        _get_comomentum_result,
        _get_market_fear_result,
        _get_spy_history_lazy,
        analyze_stock,
    )

    _get_spy_history_lazy()
    _get_market_fear_result()
    _get_comomentum_result()
    for symbol in _popular_symbols():
        try:
            analyze_stock(symbol, force_refresh=True)
        except Exception as exc:
            print(f"Background analysis refresh failed for {symbol}: {exc}")


def _worker() -> None:
    interval = max(int(os.environ.get("ANALYSIS_REFRESH_SECONDS", "3600")), 300)
    while not _stop_event.is_set():
        run_maintenance_once()
        _stop_event.wait(interval)


def start_background_maintenance() -> bool:
    global _started
    if not _enabled():
        return False
    with _lock:
        if _started:
            return False
        from codes.services import analysis_jobs
        threading.Thread(target=_worker, name="analysis-maintenance", daemon=True).start()
        threading.Thread(target=analysis_jobs.work_forever, args=(_stop_event,), name="analysis-jobs", daemon=True).start()
        _started = True
    return True


def run_forever() -> None:
    def stop(_signum, _frame):
        _stop_event.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    if not start_background_maintenance():
        raise RuntimeError("Analysis worker role is not enabled")
    _stop_event.wait()


if __name__ == "__main__":
    run_forever()
