"""
Standalone SEC refresh worker.

Owns all outbound SEC EDGAR communication. Run as a nightly cron job or
Celery beat task — never imported by the Dash app process.

Usage:
    python -m codes.workers.sec_refresh_worker
"""

import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from codes.data import db, sec_data
from codes.engine import universe

_MIN_GAP_SECONDS = 0.34   # ~3 req/sec, matches screener.py's existing SEC rate limit


def _rate_wait(last_call: list[float]) -> None:
    gap = _MIN_GAP_SECONDS - (time.time() - last_call[0])
    if gap > 0:
        time.sleep(gap)
    last_call[0] = time.time()


def run_sweep(max_symbols: int | None = None) -> None:
    try:
        # ISSUE_126: worker credentials are intentionally unable to execute
        # schema DDL; a missing release migration must stop the sweep.
        db.verify_market_database()
        # ISSUE_003: use the validated Graham-eligible universe (excludes
        # ETFs/funds/trusts/SPACs via filer-type classification) instead of
        # the raw SEC ticker list, so CompanyFacts is never downloaded for
        # non-operating entities.
        symbols = universe.get_graham_eligible_universe()
        if max_symbols:
            symbols = symbols[:max_symbols]

        print(f"[SECWorker] sweeping {len(symbols)} symbols...")
        last_call = [0.0]
        refreshed = skipped = failed = 0

        for i, sym in enumerate(symbols, 1):
            try:
                if sec_data.is_cache_stale(sym):
                    _rate_wait(last_call)
                    sec_data.fetch_company_facts(sym, include_delisted_warning=False)
                    refreshed += 1
                else:
                    skipped += 1
            except Exception as e:
                failed += 1
                print(f"  [SECWorker] ⚠️  {sym} failed: {e}")

            if i % 200 == 0:
                print(f"  [SECWorker] progress {i}/{len(symbols)} "
                    f"(refreshed={refreshed}, skipped={skipped}, failed={failed})")

        print(f"[SECWorker] done. refreshed={refreshed}, skipped={skipped}, failed={failed}")
    except Exception as e:
        print(f"[SECWorker] fatal error: {e}")
        return


if __name__ == "__main__":
    run_sweep()
