"""Resumable CLI for Track E FMP backfills."""

from __future__ import annotations

import argparse
import json

from codes.data import temporal
from codes.data.providers.fmp import FMPClient
from codes.services.track_e_ingestion import (
    ingest_fx,
    ingest_reference_data,
    ingest_symbol,
    ingest_universe,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--fx", action="append", default=[])
    parser.add_argument("--universe", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--reference-data", action="store_true")
    args = parser.parse_args()
    client = FMPClient()
    result = {"symbols": [], "fx": {}, "universes": {}}
    if args.reference_data:
        result["reference_data"] = ingest_reference_data(client)
    for dataset, items, callback, target in (
        ("symbol", args.symbol, lambda item: ingest_symbol(item, client), result["symbols"]),
        ("fx", args.fx, lambda item: ingest_fx(item, client), result["fx"]),
        ("universe", args.universe, lambda item: ingest_universe(item, client), result["universes"]),
    ):
        for item in items:
            if not args.force and temporal.checkpoint_complete(dataset, item):
                continue
            temporal.checkpoint(dataset, item, status="running")
            try:
                value = callback(item)
                rows = sum(v for v in value.values() if isinstance(v, int)) if isinstance(value, dict) else int(value)
                temporal.checkpoint(dataset, item, status="complete", rows_written=rows)
                target.append(value) if isinstance(target, list) else target.__setitem__(item, value)
            except Exception as exc:
                temporal.checkpoint(dataset, item, status="failed", error=f"{type(exc).__name__}: {exc}")
                raise
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
