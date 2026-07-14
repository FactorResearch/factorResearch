"""Bounded in-process RED and analysis metrics for operational snapshots."""

from collections import Counter, deque
from threading import Lock
import os
import time

_WINDOW = 500
_samples = deque(maxlen=_WINDOW)
_payloads = deque(maxlen=_WINDOW)
_failures = Counter()
_requests = deque(maxlen=_WINDOW)
_lock = Lock()
_started_at = time.time()
_MAX_FAILURE_KEYS = 128


def record_analysis(duration_ms: float, cache_hit: bool, payload_bytes: int = 0) -> None:
    with _lock:
        _samples.append((float(duration_ms), bool(cache_hit), int(payload_bytes)))


def record_payload(payload_bytes: int) -> None:
    with _lock:
        _payloads.append(int(payload_bytes))


def record_failure(component: str, error: BaseException) -> None:
    with _lock:
        key = (str(component)[:120], type(error).__name__)
        _failures[key] += 1
        while len(_failures) > _MAX_FAILURE_KEYS:
            del _failures[min(_failures, key=_failures.get)]


def record_request(route: str, method: str, status: int, duration_ms: float) -> None:
    with _lock:
        _requests.append((str(route)[:160], str(method)[:8], int(status), float(duration_ms)))


def snapshot() -> dict:
    with _lock:
        samples = list(_samples)
        payloads = list(_payloads)
        failures = dict(_failures)
        requests = list(_requests)
    if not samples:
        analysis = {"count": 0, "p50_ms": None, "p95_ms": None, "cache_hit_rate": None, "avg_payload_bytes": None,
                    "failures": {f"{component}:{error}": count for (component, error), count in failures.items()}}
    else:
        durations = sorted(item[0] for item in samples)
        percentile = lambda value: durations[min(round((len(durations) - 1) * value), len(durations) - 1)]
        analysis = {
            "count": len(samples),
            "p50_ms": round(percentile(0.50), 2),
            "p95_ms": round(percentile(0.95), 2),
            "cache_hit_rate": round(sum(item[1] for item in samples) / len(samples), 4),
            "avg_payload_bytes": round(sum(payloads) / len(payloads)) if payloads else None,
            "failures": {f"{component}:{error}": count for (component, error), count in failures.items()},
        }
    request_durations = sorted(item[3] for item in requests)
    request_percentile = lambda value: request_durations[min(round((len(request_durations) - 1) * value), len(request_durations) - 1)]
    routes = Counter((route, method, status // 100) for route, method, status, _duration in requests)
    return {
        "process": {"pid": os.getpid(), "uptime_seconds": round(time.time() - _started_at, 1)},
        "requests": {
            "count": len(requests),
            "error_rate": round(sum(status >= 500 for _route, _method, status, _duration in requests) / len(requests), 4) if requests else None,
            "p50_ms": round(request_percentile(0.50), 2) if requests else None,
            "p95_ms": round(request_percentile(0.95), 2) if requests else None,
            "routes": {f"{method} {route} {status_class}xx": count for (route, method, status_class), count in routes.items()},
        },
        "analysis": analysis,
    }
