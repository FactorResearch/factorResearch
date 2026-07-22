#!/usr/bin/env python3
"""Fail on new forbidden dependency directions or protected-layer cycles."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODES = ROOT / "codes"
DOMAIN_FILES = {
    *list((CODES / "domain").glob("*.py")),
    *list((CODES / "models").glob("*.py")),
    CODES / "core" / "engine_contracts.py",
    CODES / "core" / "financial_math.py",
    CODES / "core" / "model_utils.py",
    CODES / "core" / "ports.py",
    CODES / "domain" / "canonical.py",
}
FORBIDDEN_EXTERNAL = {
    "dash",
    "finnhub",
    "flask",
    "psycopg",
    "psycopg2",
    "redis",
    "requests",
    "stripe",
}
FORBIDDEN_INTERNAL_PREFIXES = (
    "codes.app",
    "codes.app_modules",
    "codes.data",
    "codes.routes",
    "codes.services",
    "codes.workers",
)
PRESENTATION_ALLOWED_DOMAIN_IMPORTS = {
    ("codes/routes/analyze.py", "codes.models.analysis_snapshot"),  # identity mapping only
}
PROTECTED_CYCLE_PREFIXES = ("codes.core", "codes.domain", "codes.models")
SERVICE_BOUNDARY_ADAPTERS = {
    "codes/api/v1.py",
    "codes/app_modules/tabs/analyze.py",
    "codes/app_modules/tabs/portfolio.py",
    "codes/app_modules/tabs/pricing.py",
    "codes/app_modules/tabs/profile.py",
    "codes/app_modules/tabs/screener.py",
    "codes/routes/analyze.py",
    "codes/routes/charts.py",
}
FORBIDDEN_ADAPTER_BUSINESS_IMPORTS = (
    "codes.billing",
    "codes.data",
    "codes.engine",
    "codes.portfolio",
)
LEGACY_UNTYPED_ENGINE_BOUNDARIES = {
    "codes/engine/backtest.py:walk_forward",
    "codes/engine/backtest.py:compare_strategies",
    "codes/engine/factor_backtest.py:run_factor_backtest",
    "codes/engine/factor_engine.py:extract_factor_scores",
    "codes/engine/factor_engine.py:persist_factor_scores",
    "codes/engine/factor_snapshot.py:history_has_sufficient_dates",
    "codes/engine/factor_snapshot.py:history_scores_asof",
    "codes/engine/factor_snapshot.py:snapshot_today",
    "codes/engine/market_fear.py:analyze",
    "codes/engine/scorer.py:composite",
    "codes/engine/scorer.py:enhanced_composite",
    "codes/engine/scorer.py:fundamental_only",
    "codes/engine/scorer.py:apply_regime_overlay",
    "codes/engine/screener.py:update_stock_after_analysis",
    "codes/engine/strategy_cache.py:get_or_run_backtest",
    "codes/engine/strategy_cache.py:strategy_hash",
    "codes/engine/user_strategy.py:compute_weighted_score",
    "codes/engine/user_strategy.py:normalize_weights",
    "codes/engine/user_strategy.py:set_user_weights",
    "codes/models/alternative_data.py:analyze_sec_8k_sentiment",
    "codes/models/alternative_data.py:get_alternative_data_score",
    "codes/models/alternative_data.py:get_hiring_velocity_signal_from_records",
    "codes/models/alternative_data.py:get_insider_trends_signal",
    "codes/models/alternative_data.py:get_institutional_ownership_signal",
    "codes/models/alternative_data.py:get_patent_activity_signal",
    "codes/models/alternative_data.py:get_sec_8k_sentiment_signal",
    "codes/models/alternative_data.py:get_supply_chain_signal",
    "codes/models/alternative_data.py:get_web_traffic_signal_from_records",
    "codes/models/altman.py:score",
    "codes/models/buffett.py:score",
    "codes/models/comomentum.py:calc_comomentum",
    "codes/models/graham.py:score",
    "codes/models/greenblatt.py:compute_single",
    "codes/models/greenblatt.py:enterprise_value",
    "codes/models/greenblatt.py:rank_universe",
    "codes/models/insider_activity.py:calc_cluster_buying_score",
    "codes/models/insider_activity.py:calc_insider_type_quality",
    "codes/models/insider_activity.py:calc_net_insider_buying",
    "codes/models/insider_activity.py:get_insider_score",
    "codes/models/momentum.py:score",
    "codes/models/piotroski.py:score",
    "codes/models/quality.py:score",
    "codes/models/regime.py:score",
    "codes/models/risk_metrics.py:score",
    "codes/models/risk_metrics.py:validate_input",
    "codes/models/risk_metrics.py:validate_output",
    "codes/models/spy_benchmark_model.py:compute_benchmark",
}


def module_name(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(module: str) -> list[str] | None:
        if module in visiting:
            start = visiting.index(module)
            return visiting[start:] + [module]
        if module in visited:
            return None
        visiting.append(module)
        for dependency in sorted(graph[module]):
            cycle = visit(dependency)
            if cycle:
                return cycle
        visiting.pop()
        visited.add(module)
        return None

    for module in sorted(graph):
        cycle = visit(module)
        if cycle:
            return cycle
    return None


def adapter_boundary_errors(relative: str, imports: set[str]) -> list[str]:
    if relative not in SERVICE_BOUNDARY_ADAPTERS:
        return []
    return [
        f"{relative}: delivery adapter bypasses application service via {imported}"
        for imported in imports
        if imported.startswith(FORBIDDEN_ADAPTER_BUSINESS_IMPORTS)
    ]


def dependency_errors(path: Path, imports: set[str]) -> list[str]:
    relative = path.relative_to(ROOT).as_posix()
    errors: list[str] = adapter_boundary_errors(relative, imports)
    if path in DOMAIN_FILES:
        for imported in imports:
            root = imported.split(".", 1)[0]
            if root in FORBIDDEN_EXTERNAL or imported.startswith(FORBIDDEN_INTERNAL_PREFIXES):
                errors.append(f"{relative}: domain imports forbidden dependency {imported}")

    if relative.startswith(("codes/app_modules/", "codes/routes/")):
        for imported in imports:
            if (
                imported.startswith("codes.models")
                and (
                    relative,
                    imported,
                )
                not in PRESENTATION_ALLOWED_DOMAIN_IMPORTS
            ):
                errors.append(f"{relative}: presentation imports domain calculation {imported}")
    if relative.startswith("codes/services/"):
        for imported in imports:
            if imported.split(".", 1)[0] in {"dash", "flask"}:
                errors.append(f"{relative}: application service imports framework {imported}")
    return errors


def boundary_annotation_errors(relative: str, source: str) -> list[str]:
    """Reject new public engine inputs without named canonical contracts.

    Existing pandas and dictionary boundaries are explicitly grandfathered so
    ISSUE_137 can ship an additive compatibility layer. Any new module-level
    public function under ``codes.engine`` or ``codes.models`` must use named
    input types rather than arbitrary dictionaries, ``Any``, ``Mapping``,
    untyped parameters, or pandas DataFrames.
    """
    if not relative.startswith(("codes/engine/", "codes/models/")):
        return []
    tree = ast.parse(source, filename=relative)
    errors: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        boundary = f"{relative}:{node.name}"
        if boundary in LEGACY_UNTYPED_ENGINE_BOUNDARIES:
            continue
        arguments = [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]
        if node.args.vararg is not None:
            arguments.append(node.args.vararg)
        if node.args.kwarg is not None:
            arguments.append(node.args.kwarg)
        for argument in arguments:
            forbidden_names = (
                {part.id for part in ast.walk(argument.annotation) if isinstance(part, ast.Name)}
                if argument.annotation is not None
                else set()
            )
            forbidden_attributes = (
                {
                    part.attr
                    for part in ast.walk(argument.annotation)
                    if isinstance(part, ast.Attribute)
                }
                if argument.annotation is not None
                else set()
            )
            if argument.annotation is None or (
                {"Any", "DataFrame", "Mapping", "dict"} & (forbidden_names | forbidden_attributes)
            ):
                errors.append(
                    f"{boundary}: parameter {argument.arg} requires a named canonical type"
                )
    return errors


def protected_cycle_error(imports_by_module: dict[str, set[str]]) -> str | None:
    protected = {
        module for module in imports_by_module if module.startswith(PROTECTED_CYCLE_PREFIXES)
    }
    graph: dict[str, set[str]] = defaultdict(set)
    for module in protected:
        graph[module].update(imports_by_module[module] & protected)
    cycle = find_cycle(graph)
    return "protected-layer import cycle: " + " -> ".join(cycle) if cycle else None


def main() -> int:
    errors: list[str] = []
    imports_by_module: dict[str, set[str]] = {}

    for path in CODES.rglob("*.py"):
        imports = imported_modules(path)
        imports_by_module[module_name(path)] = imports
        errors.extend(dependency_errors(path, imports))
        errors.extend(
            boundary_annotation_errors(
                path.relative_to(ROOT).as_posix(),
                path.read_text(encoding="utf-8"),
            )
        )

    cycle_error = protected_cycle_error(imports_by_module)
    if cycle_error:
        errors.append(cycle_error)

    if errors:
        print("Architecture gate failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Architecture boundaries and protected-layer cycles: passing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
