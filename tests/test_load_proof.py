import csv
import importlib.util
from pathlib import Path


def _module():
    spec = importlib.util.spec_from_file_location("evaluate_load", "scripts/evaluate-load.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stats(path: Path, requests: int, failures: int, p95: int):
    with path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=["Name", "Request Count", "Failure Count", "95%"])
        writer.writeheader()
        writer.writerow({"Name": "Aggregated", "Request Count": requests, "Failure Count": failures, "95%": p95})


def test_load_evaluator_passes_within_contract(tmp_path):
    path = tmp_path / "stats.csv"
    _stats(path, 1000, 1, 700)
    result = _module().evaluate(path, max_p95_ms=750, max_failure_rate=0.001)
    assert result["passed"]


def test_load_evaluator_fails_latency_or_errors(tmp_path):
    path = tmp_path / "stats.csv"
    _stats(path, 100, 2, 900)
    result = _module().evaluate(path, max_p95_ms=750, max_failure_rate=0.001)
    assert not result["passed"]
    assert result["checks"] == {"requests_recorded": True, "p95_ms": False, "failure_rate": False}


def test_workload_documents_all_required_profiles():
    content = Path("load/README.md").read_text()
    for profile in ("Baseline", "Expected peak", "Stress", "Spike", "Soak", "Long soak"):
        assert profile in content
