"""Small lazy, bounded connection pool for DB-API connections."""

from __future__ import annotations

import os
import queue
import threading
from contextlib import contextmanager
from collections.abc import Callable, Iterator


class ConnectionPool:
    def __init__(self, connect: Callable[[], object], *, max_size: int = 5, timeout: float = 10):
        self._connect = connect
        self._max_size = max(1, max_size)
        self._timeout = timeout
        self._available = queue.LifoQueue(self._max_size)
        self._created = 0
        self._pid = os.getpid()
        self._lock = threading.Lock()

    def _reset_after_fork(self) -> None:
        if self._pid == os.getpid():
            return
        with self._lock:
            if self._pid != os.getpid():
                self._available = queue.LifoQueue(self._max_size)
                self._created = 0
                self._pid = os.getpid()

    def _acquire(self):
        self._reset_after_fork()
        try:
            return self._available.get_nowait()
        except queue.Empty:
            with self._lock:
                if self._created < self._max_size:
                    self._created += 1
                    try:
                        return self._connect()
                    except Exception:
                        self._created -= 1
                        raise
            return self._available.get(timeout=self._timeout)

    def _release(self, connection) -> None:
        if getattr(connection, "closed", False) or getattr(connection, "broken", False):
            with self._lock:
                self._created -= 1
            return
        try:
            self._available.put_nowait(connection)
        except queue.Full:
            connection.close()
            with self._lock:
                self._created -= 1

    @contextmanager
    def connection(self) -> Iterator:
        connection = self._acquire()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            self._release(connection)

    def check_connection(self) -> None:
        """Open and release one connection so configuration failures surface now."""
        connection = self._acquire()
        self._release(connection)

    def stats(self) -> dict:
        self._reset_after_fork()
        with self._lock:
            created = self._created
        available = self._available.qsize()
        return {
            "created": created,
            "available": available,
            "in_use": max(created - available, 0),
            "max_size": self._max_size,
            "utilization": round((created - available) / self._max_size, 4),
        }
