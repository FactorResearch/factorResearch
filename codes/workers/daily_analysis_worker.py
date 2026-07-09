from __future__ import annotations

from collections.abc import Callable, Iterable

from codes.models.analysis_snapshot import AnalysisType
from codes.services.analysis_snapshot_service import save_standard_snapshot


def run_daily_standard_analysis(
    symbols: Iterable[str],
    analyze: Callable[[str], dict],
    *,
    algorithm_version: str = "standard-v1",
) -> list[str]:
    saved: list[str] = []
    for symbol in symbols:
        result = analyze(symbol)
        snapshot = save_standard_snapshot(
            result,
            analysis_type=AnalysisType.STANDARD,
            algorithm_version=algorithm_version,
        )
        if snapshot:
            saved.append(snapshot.public_path)
    return saved

