import json
import math
import os
import time
from pathlib import Path

CACHE_DIR = Path(".cache")
CACHE_TTL = 6 * 30 * 24 * 60 * 60  # 6 months in seconds

CACHE_DIR.mkdir(exist_ok=True)


def _path(kind: str, key: str) -> Path:
    return CACHE_DIR / f"{kind}-{key.lower()}.json"


# ── JSON encoder that handles numpy / pandas scalar types ─────────────────────

class _SafeEncoder(json.JSONEncoder):
    """
    Converts types that the stdlib json module can't handle:
      - numpy bool_   → Python bool
      - numpy int*    → Python int
      - numpy float*  → Python float  (nan/inf → None)
      - numpy ndarray → list
      - pandas NA / NaT → None
      - plain Python float nan/inf → None
    """

    def default(self, obj):
        # numpy types
        try:
            import numpy as np
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                v = float(obj)
                return None if not math.isfinite(v) else v
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass

        # pandas NA / NaT
        try:
            import pandas as pd
            if obj is pd.NA or obj is pd.NaT:
                return None
        except ImportError:
            pass

        return super().default(obj)

    def iterencode(self, o, _one_shot=False):
        """Sanitise plain Python floats (nan/inf) before encoding."""
        return super().iterencode(self._sanitise(o), _one_shot)

    def _sanitise(self, obj):
        """Recursively replace non-finite floats with None."""
        if isinstance(obj, float):
            return None if not math.isfinite(obj) else obj
        if isinstance(obj, dict):
            return {k: self._sanitise(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._sanitise(v) for v in obj]
        return obj


def _dumps(data) -> str:
    return json.dumps({"ts": time.time(), "data": data}, indent=2, cls=_SafeEncoder)


# ── Public API ────────────────────────────────────────────────────────────────

def read(kind: str, key: str):
    p = _path(kind, key)
    try:
        if p.exists():
            entry = json.loads(p.read_text())
            age = time.time() - entry["ts"]
            if age < CACHE_TTL:
                days_left = int((CACHE_TTL - age) / 86400)
                print(f"[CACHE HIT] {kind}:{key} ({days_left} days left)")
                return entry["data"]
            print(f"[CACHE EXPIRED] {kind}:{key}")
    except Exception:
        pass
    return None


def write(kind: str, key: str, data) -> None:
    try:
        _path(kind, key).write_text(_dumps(data))
        print(f"[CACHE SAVED] {kind}:{key}")
    except Exception as e:
        print(f"[CACHE ERROR] {e}")


def list_cached_stocks() -> list[str]:
    return sorted(
        p.stem.replace("quote-", "").upper()
        for p in CACHE_DIR.glob("quote-*.json")
    )


def list_cached_kind(kind: str) -> list[str]:
    """Return all keys stored under a given cache kind, e.g. 'analysis'."""
    prefix = f"{kind}-"
    return sorted(
        p.stem[len(prefix):].upper()
        for p in CACHE_DIR.glob(f"{prefix}*.json")
    )


def clear(kind: str, key: str) -> None:
    p = _path(kind, key)
    if p.exists():
        p.unlink()
        print(f"[CACHE CLEARED] {kind}:{key}")