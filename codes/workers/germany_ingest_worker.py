"""Import verified Germany financial bundles into the market database.

Usage: python -m codes.workers.germany_ingest_worker --symbol SAP.DE --bundle-dir /path/SAP.DE
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from codes.data.providers.germany_ingestion import GermanyVerifiedCsvBundle, import_germany_verified_csv_bundle  # noqa: E402
from codes.data.providers.germany_normalization import PUBLIC_CONFIDENCE  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import source-verified Germany financials.")
    parser.add_argument("--symbol", required=True, help="Germany symbol, e.g. SAP.DE or SAP:XETRA")
    parser.add_argument("--bundle-dir", type=Path, help="Directory containing company.csv, periods.csv, documents.csv, facts.csv, and shares.csv.")
    for name in ("company", "periods", "documents", "facts", "shares"):
        parser.add_argument(f"--{name}-csv", type=Path)
    parser.add_argument("--allow-internal", action="store_true", help="Store provider_normalized_internal_only data for internal QA only.")
    return parser


def run_from_args(args: argparse.Namespace) -> int:
    bundle = GermanyVerifiedCsvBundle(*(_bundle_path(args, f"{name}_csv", f"{name}.csv") for name in ("company", "periods", "documents", "facts", "shares")))
    missing = [(name, path) for name, path in zip(("company CSV", "periods CSV", "documents CSV", "facts CSV", "shares CSV"), bundle.__dict__.values()) if path is None or not path.is_file()]
    if missing:
        print("[GermanyIngest] input bundle is incomplete. This worker imports verified regulator, issuer, or licensed exports; it does not scrape source sites.", file=sys.stderr)
        for name, path in missing: print(f"  missing {name}: {path}", file=sys.stderr)
        print("See docs/track_b_germany.md for the required CSV schemas.", file=sys.stderr)
        return 2
    try:
        result = import_germany_verified_csv_bundle(args.symbol, bundle, allow_internal=args.allow_internal)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[GermanyIngest] validation failed: {exc}", file=sys.stderr)
        print("[GermanyIngest] No source facts were written.", file=sys.stderr)
        return 2
    status = "public_score_ready" if result.can_score and result.quality_report.confidence in PUBLIC_CONFIDENCE else "stored_internal_only" if result.can_score else "stored_quality_failed"
    print(f"[GermanyIngest] {result.symbol} {status} target=market_db source=verified_csv confidence={result.quality_report.confidence} issues={len(result.quality_report.issues)}")
    return 0 if result.can_score or args.allow_internal else 2


def _bundle_path(args: argparse.Namespace, attribute: str, filename: str) -> Path | None:
    value = getattr(args, attribute)
    return value if value is not None else args.bundle_dir / filename if args.bundle_dir is not None else None


def main(argv: list[str] | None = None) -> int:
    return run_from_args(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
