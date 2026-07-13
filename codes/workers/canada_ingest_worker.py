"""Standalone Canada verified-source ingestion worker.

This worker imports structured exports from a verified Canada extraction
process into the market database. It does not scrape SEDAR+ and should not be
imported by the Dash app process.

Usage:
    python -m codes.workers.canada_ingest_worker \
        --symbol SHOP.TO \
        --company-csv company.csv \
        --periods-csv periods.csv \
        --documents-csv documents.csv \
        --facts-csv facts.csv \
        --shares-csv shares.csv
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from codes.data.providers.canada_ingestion import (  # noqa: E402
    CanadaVerifiedCsvBundle,
    import_canada_verified_csv_bundle,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import verified Canada source exports.")
    parser.add_argument("--symbol", required=True, help="Canadian symbol, e.g. SHOP.TO or SHOP:TSX")
    parser.add_argument("--company-csv", required=True, type=Path)
    parser.add_argument("--periods-csv", required=True, type=Path)
    parser.add_argument("--documents-csv", required=True, type=Path)
    parser.add_argument("--facts-csv", required=True, type=Path)
    parser.add_argument("--shares-csv", required=True, type=Path)
    parser.add_argument(
        "--allow-internal",
        action="store_true",
        help="Allow provider_normalized_internal_only payloads for internal QA storage.",
    )
    return parser


def run_from_args(args: argparse.Namespace) -> int:
    bundle = CanadaVerifiedCsvBundle(
        company_csv=args.company_csv,
        periods_csv=args.periods_csv,
        documents_csv=args.documents_csv,
        facts_csv=args.facts_csv,
        shares_csv=args.shares_csv,
    )
    result = import_canada_verified_csv_bundle(
        args.symbol,
        bundle,
        allow_internal=args.allow_internal,
    )
    status = "score_ready" if result.can_score else "stored_quality_failed"
    print(
        f"[CanadaIngest] {result.symbol} {status} "
        f"confidence={result.quality_report.confidence} "
        f"issues={len(result.quality_report.issues)}"
    )
    return 0 if result.can_score or args.allow_internal else 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    return run_from_args(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
