import os
import socket

import pytest


# Importing codes.app must not connect to databases or providers during test
# collection. Tests that exercise startup call it explicitly with mocks.
os.environ["APP_SKIP_STARTUP"] = "1"
os.environ["APP_FEATURE_FLAG"] = "V1"


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch, request):
    """Tests are hermetic unless explicitly marked for live-network validation."""
    if request.node.get_closest_marker("live_network"):
        return
    original = socket.getaddrinfo

    def local_only(host, *args, **kwargs):
        if host not in {"localhost", "127.0.0.1", "::1"}:
            raise OSError(f"External network disabled during tests: {host}")
        return original(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", local_only)
