"""Queue model recomputation for stocks that already exist in analysis storage."""

from codes.services.analysis_jobs import enqueue_existing_stock_backfill


if __name__ == "__main__":
    print(f"queued={enqueue_existing_stock_backfill()}")
