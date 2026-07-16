"""Bounded in-process RED and analysis metrics for operational snapshots."""

import os
import time
from collections import Counter, deque
from threading import Lock

_WINDOW = 500
_samples = deque(maxlen=_WINDOW)
_payloads = deque(maxlen=_WINDOW)
_failures = Counter()
_requests = deque(maxlen=_WINDOW)
_ui_operations = deque(maxlen=_WINDOW)
_web_vitals = deque(maxlen=_WINDOW)
_lock = Lock()
_started_at = time.time()
_MAX_FAILURE_KEYS = 128
WEB_VITAL_BUDGETS = {"LCP": 2500.0, "INP": 200.0, "CLS": 0.1}


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


def record_ui_operation(
    operation: str,
    duration_ms: float,
    *,
    outcome: str = "success",
    section: str = "",
    retries: int = 0,
    stale_fallback: bool = False,
    first_useful_ms: float | None = None,
) -> None:
    """Record privacy-safe UX latency without symbols, names, or user input."""
    allowed_outcomes = {"success", "partial", "error", "cancelled", "empty"}
    normalized_outcome = outcome if outcome in allowed_outcomes else "error"
    with _lock:
        _ui_operations.append(
            (
                str(operation)[:80],
                str(section)[:80],
                normalized_outcome,
                max(0.0, float(duration_ms)),
                max(0, int(retries)),
                bool(stale_fallback),
                None if first_useful_ms is None else max(0.0, float(first_useful_ms)),
            )
        )


def record_web_vital(
    name: str,
    value: float,
    *,
    route: str,
    device: str,
    navigation_type: str = "navigate",
) -> bool:
    """Record bounded, identifier-free real-user UX measurements."""
    metric = str(name).upper()
    if metric not in WEB_VITAL_BUDGETS:
        return False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    upper_bound = 10.0 if metric == "CLS" else 120_000.0
    if numeric < 0 or numeric > upper_bound:
        return False
    normalized_device = device if device in {"mobile", "tablet", "desktop"} else "unknown"
    normalized_route = str(route or "/unknown").split("?", 1)[0][:80]
    with _lock:
        _web_vitals.append(
            (metric, round(numeric, 4), normalized_route, normalized_device, str(navigation_type)[:32])
        )
    return True


def snapshot() -> dict:
    with _lock:
        samples = list(_samples)
        payloads = list(_payloads)
        failures = dict(_failures)
        requests = list(_requests)
        ui_operations = list(_ui_operations)
        web_vitals = list(_web_vitals)
    if not samples:
        analysis = {
            "count": 0,
            "p50_ms": None,
            "p95_ms": None,
            "cache_hit_rate": None,
            "avg_payload_bytes": None,
            "failures": {
                f"{component}:{error}": count for (component, error), count in failures.items()
            },
        }
    else:
        durations = sorted(item[0] for item in samples)
        def percentile(value):
            return durations[
                min(round((len(durations) - 1) * value), len(durations) - 1)
            ]
        analysis = {
            "count": len(samples),
            "p50_ms": round(percentile(0.50), 2),
            "p95_ms": round(percentile(0.95), 2),
            "cache_hit_rate": round(sum(item[1] for item in samples) / len(samples), 4),
            "avg_payload_bytes": round(sum(payloads) / len(payloads)) if payloads else None,
            "failures": {
                f"{component}:{error}": count for (component, error), count in failures.items()
            },
        }
    request_durations = sorted(item[3] for item in requests)
    def request_percentile(value):
        return request_durations[
            min(round((len(request_durations) - 1) * value), len(request_durations) - 1)
        ]
    routes = Counter(
        (route, method, status // 100) for route, method, status, _duration in requests
    )
    ui_durations = sorted(item[3] for item in ui_operations)

    def ui_percentile(value: float) -> float | None:
        if not ui_durations:
            return None
        return round(
            ui_durations[min(round((len(ui_durations) - 1) * value), len(ui_durations) - 1)], 2
        )

    ui_outcomes = Counter(item[2] for item in ui_operations)
    useful = sorted(item[6] for item in ui_operations if item[6] is not None)
    vital_groups: dict[tuple[str, str, str], list[float]] = {}
    for metric, value, route, device, _navigation in web_vitals:
        vital_groups.setdefault((route, device, metric), []).append(value)
    vital_summary = {}
    for (route, device, metric), values in vital_groups.items():
        ordered = sorted(values)
        p75 = ordered[min(round((len(ordered) - 1) * 0.75), len(ordered) - 1)]
        vital_summary[f"{device}:{route}:{metric}"] = {
            "count": len(values),
            "p75": round(p75, 4),
            "budget": WEB_VITAL_BUDGETS[metric],
            "passing": p75 <= WEB_VITAL_BUDGETS[metric],
        }
    return {
        "process": {"pid": os.getpid(), "uptime_seconds": round(time.time() - _started_at, 1)},
        "requests": {
            "count": len(requests),
            "error_rate": round(
                sum(status >= 500 for _route, _method, status, _duration in requests)
                / len(requests),
                4,
            )
            if requests
            else None,
            "p50_ms": round(request_percentile(0.50), 2) if requests else None,
            "p95_ms": round(request_percentile(0.95), 2) if requests else None,
            "routes": {
                f"{method} {route} {status_class}xx": count
                for (route, method, status_class), count in routes.items()
            },
        },
        "analysis": analysis,
        "ui_operations": {
            "count": len(ui_operations),
            "p50_ms": ui_percentile(0.50),
            "p75_ms": ui_percentile(0.75),
            "p95_ms": ui_percentile(0.95),
            "first_useful_p75_ms": (
                round(useful[min(round((len(useful) - 1) * 0.75), len(useful) - 1)], 2)
                if useful
                else None
            ),
            "outcomes": dict(ui_outcomes),
            "retry_count": sum(item[4] for item in ui_operations),
            "stale_fallback_count": sum(item[5] for item in ui_operations),
            "sections": dict(Counter(item[1] for item in ui_operations if item[1])),
        },
        "web_vitals": {
            "count": len(web_vitals),
            "budgets": WEB_VITAL_BUDGETS,
            "segments": vital_summary,
            "regressions": sorted(
                key for key, value in vital_summary.items() if not value["passing"]
            ),
        },
    }
