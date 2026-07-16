#!/usr/bin/env python3
"""Fail on new forbidden dependency directions or protected-layer cycles."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODES = ROOT / "codes"
DOMAIN_FILES = {
    *list((CODES / "models").glob("*.py")),
    CODES / "core" / "engine_contracts.py",
    CODES / "core" / "financial_math.py",
    CODES / "core" / "model_utils.py",
    CODES / "core" / "ports.py",
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
PROTECTED_CYCLE_PREFIXES = ("codes.core", "codes.models")
SERVICE_BOUNDARY_ADAPTERS = {
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
