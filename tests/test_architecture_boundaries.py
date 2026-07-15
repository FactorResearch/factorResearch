from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTTP_ADAPTERS = {
    ROOT / "codes/auth.py",
    ROOT / "codes/data/api_fetcher.py",
    ROOT / "codes/data/sec_data.py",
    ROOT / "codes/engine/universe.py",
}


def test_direct_http_calls_stay_in_adapters():
    offenders = []
    for path in (ROOT / "codes").rglob("*.py"):
        if path in HTTP_ADAPTERS or (ROOT / "codes/data/providers") in path.parents:
            continue
        source = path.read_text()
        if any(call in source for call in ("requests.get(", "requests.post(", "requests.put(", "requests.delete(")):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []
