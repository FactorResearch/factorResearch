"""Small dependency-free concurrent load probe for deployed Analyze routes."""

from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import time
import urllib.request


def request(url: str) -> tuple[float, int]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            response.read()
            return (time.perf_counter() - started) * 1000, response.status
    except Exception:
        return (time.perf_counter() - started) * 1000, 0


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(round((len(ordered) - 1) * fraction), len(ordered) - 1)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Example: http://127.0.0.1:8050/analyze/AAPL/")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        results = list(executor.map(lambda _index: request(args.url), range(args.requests)))
    durations = [duration for duration, _status in results]
    successes = sum(status == 200 for _duration, status in results)
    print({
        "requests": len(results),
        "success_rate": round(successes / len(results), 4),
        "mean_ms": round(statistics.mean(durations), 2),
        "p50_ms": round(percentile(durations, 0.50), 2),
        "p95_ms": round(percentile(durations, 0.95), 2),
        "p99_ms": round(percentile(durations, 0.99), 2),
    })


if __name__ == "__main__":
    main()
