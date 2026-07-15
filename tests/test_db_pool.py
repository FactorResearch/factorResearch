from concurrent.futures import ThreadPoolExecutor

import pytest

from codes.core.db_pool import ConnectionPool


class FakeConnection:
    closed = False

    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_pool_reuses_connection_and_commits_transactions():
    created = []
    pool = ConnectionPool(lambda: created.append(FakeConnection()) or created[-1], max_size=1)
    with pool.connection() as first:
        pass
    with pool.connection() as second:
        pass
    assert first is second
    assert first.commits == 2
    assert len(created) == 1


def test_pool_rolls_back_and_reuses_failed_transaction():
    connection = FakeConnection()
    pool = ConnectionPool(lambda: connection, max_size=1)
    with pytest.raises(RuntimeError):
        with pool.connection():
            raise RuntimeError("failed")
    with pool.connection() as reused:
        pass
    assert reused is connection
    assert connection.rollbacks == 1


def test_pool_never_creates_more_than_max_size():
    created = []
    pool = ConnectionPool(lambda: created.append(FakeConnection()) or created[-1], max_size=2)

    def use_connection():
        with pool.connection() as connection:
            return connection

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: use_connection(), range(20)))
    assert len(created) <= 2
