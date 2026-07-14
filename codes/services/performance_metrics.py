"""Small in-process analysis latency and cache-efficiency window."""

from collections import deque
from threading import Lock

_WINDOW = 500
_samples = deque(maxlen=_WINDOW)
_payloads = deque(maxlen=_WINDOW)
_lock = Lock()


def record_analysis(duration_ms: float, cache_hit: bool, payload_bytes: int = 0) -> None:
    with _lock:
        _samples.append((float(duration_ms), bool(cache_hit), int(payload_bytes)))


def record_payload(payload_bytes: int) -> None:
    with _lock:
        _payloads.append(int(payload_bytes))


def snapshot() -> dict:
    with _lock:
        samples = list(_samples)
        payloads = list(_payloads)
    if not samples:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "cache_hit_rate": None, "avg_payload_bytes": None}
    durations = sorted(item[0] for item in samples)
    percentile = lambda value: durations[min(round((len(durations) - 1) * value), len(durations) - 1)]
    return {
        "count": len(samples),
        "p50_ms": round(percentile(0.50), 2),
        "p95_ms": round(percentile(0.95), 2),
        "cache_hit_rate": round(sum(item[1] for item in samples) / len(samples), 4),
        "avg_payload_bytes": round(sum(payloads) / len(payloads)) if payloads else None,
    }
