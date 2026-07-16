from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from codes.composition import compose_runtime
from codes.core.ports import AnalysisRepository, Clock, IdGenerator, QuoteReader

ROOT = Path(__file__).resolve().parents[1]


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 7, 16, tzinfo=UTC)

    def monotonic(self) -> float:
        return 42.5


class FixedIds:
    def new_id(self) -> str:
        return "request-076"


class MemoryQuoteReader:
    def get_quote(self, symbol: str) -> Mapping[str, float | str | None]:
        return {"symbol": symbol, "price": 101.25, "currency": "USD"}


class AlternateQuoteReader:
    def get_quote(self, symbol: str) -> Mapping[str, float | str | None]:
        return {"symbol": symbol, "price": 101.25, "currency": "USD"}


class MemoryAnalysisRepository:
    def __init__(self) -> None:
        self.items: dict[str, Mapping[str, object]] = {}

    def get_latest(self, symbol: str) -> Mapping[str, object] | None:
        return self.items.get(symbol)

    def save(self, symbol: str, analysis: Mapping[str, object]) -> None:
        self.items[symbol] = dict(analysis)


def assert_quote_reader_contract(reader: QuoteReader) -> None:
    quote = reader.get_quote("AAPL")
    assert quote["symbol"] == "AAPL"
    assert quote["price"] == 101.25
    assert quote["currency"] == "USD"


def assert_repository_contract(repository: AnalysisRepository) -> None:
    assert repository.get_latest("AAPL") is None
    repository.save("AAPL", {"score": 76.0, "currency": "USD"})
    assert repository.get_latest("AAPL") == {"score": 76.0, "currency": "USD"}


def test_backend_composition_root_accepts_deterministic_ports() -> None:
    clock: Clock = FixedClock()
    ids: IdGenerator = FixedIds()

    runtime = compose_runtime(clock=clock, ids=ids)

    assert runtime.clock.now() == datetime(2026, 7, 16, tzinfo=UTC)
    assert runtime.clock.monotonic() == 42.5
    assert runtime.ids.new_id() == "request-076"


def test_quote_adapters_are_interchangeable_under_shared_contract() -> None:
    for reader in (MemoryQuoteReader(), AlternateQuoteReader()):
        assert_quote_reader_contract(reader)


def test_repository_adapter_obeys_shared_contract() -> None:
    assert_repository_contract(MemoryAnalysisRepository())


def test_architecture_and_duplication_gates_pass() -> None:
    for script in ("check-architecture.py", "check-duplication.py"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
