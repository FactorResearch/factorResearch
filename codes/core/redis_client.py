import os
import json
import threading

try:
    import redis as _redis_lib
except ImportError:
    _redis_lib = None

_REDIS_URL = os.environ.get("REDIS_URL")
_client = None
_lock = threading.Lock()


def get_redis():
    global _client

    if not _REDIS_URL or _redis_lib is None:
        return None

    if _client is not None:
        return _client or None

    with _lock:
        if _client is not None:
            return _client or None

        try:
            _client = _redis_lib.from_url(_REDIS_URL, decode_responses=True)
            _client.ping()
        except Exception as e:
            print(f"[Redis] connection failed -> fallback: {e}")
            _client = False

    return _client or None


def json_get(r, key):
    try:
        val = r.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


def json_set(r, key, value, ex=None):
    try:
        r.set(key, json.dumps(value, default=str), ex=ex)
    except Exception as e:
        print(f"[Redis] write failed {key}: {e}")