#!/usr/bin/env python3
"""Produce a reproducible architecture/debt report and enforce critical boundaries."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
CODES = ROOT / "codes"
DOMAIN_FILES = {
    *list((CODES / "models").glob("*.py")),
    CODES / "core" / "engine_contracts.py",
    CODES / "core" / "financial_math.py",
    CODES / "core" / "model_utils.py",
    CODES / "core" / "ports.py",
}
INFRA_IMPORT_ROOTS = {
    "dash",
    "finnhub",
    "flask",
    "psycopg",
    "psycopg2",
    "redis",
    "requests",
    "stripe",
}
PRESENTATION_PREFIXES = ("codes/app_modules/", "codes/routes/")
PRESENTATION_DOMAIN_ALLOWLIST = {
    ("codes/routes/analyze.py", "codes.models.analysis_snapshot"),
}


def python_paths() -> list[Path]:
    return sorted(CODES.rglob("*.py"))


def module_name(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


def imports(tree: ast.AST) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def decision_complexity(node: ast.AST) -> int:
    decisions = (
        ast.AsyncFor,
        ast.BoolOp,
        ast.ExceptHandler,
        ast.For,
        ast.If,
        ast.IfExp,
        ast.Match,
        ast.Try,
        ast.While,
    )
    return 1 + sum(isinstance(child, decisions) for child in ast.walk(node))


def is_domain_path(path: Path) -> bool:
    return path in DOMAIN_FILES


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: set[tuple[str, ...]] = set()

    def canonical(items: list[str]) -> tuple[str, ...]:
        ring = items[:-1]
        rotations = [tuple(ring[index:] + ring[:index]) for index in range(len(ring))]
        return min(rotations)

    def visit(module: str, path: list[str]) -> None:
        if module in path:
            start = path.index(module)
            cycles.add(canonical(path[start:] + [module]))
            return
        if len(path) > 30:
            return
        for dependency in graph.get(module, set()):
            visit(dependency, path + [module])

    for module in graph:
        visit(module, [])
    return [list(cycle) + [cycle[0]] for cycle in sorted(cycles)]


def changed_files() -> list[dict[str, int | str]]:
    command = ["git", "log", "--format=", "--name-only", "--", "codes"]
    result = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    counts = Counter(line for line in result.stdout.splitlines() if line.startswith("codes/"))
    return [
        {"path": path, "commits_touching_file": count} for path, count in counts.most_common(20)
    ]


def duplicate_functions(
    functions: Iterable[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]],
) -> list[list[str]]:
    bodies: dict[str, list[str]] = defaultdict(list)
    for path, node in functions:
        body = node.body[1:] if ast.get_docstring(node) else node.body
        size = sum(1 for statement in body for _ in ast.walk(statement))
        if size < 18:
            continue
        fingerprint = ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)
        bodies[fingerprint].append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.name}")
    return sorted(locations for locations in bodies.values() if len(locations) > 1)


def dependency_findings(
    path: Path, relative: str, imported: set[str]
) -> tuple[list[str], list[str], list[str]]:
    domain_infra: list[str] = []
    presentation_domain: list[str] = []
    service_framework: list[str] = []
    for imported_module in imported:
        root = imported_module.split(".", 1)[0]
        if is_domain_path(path) and root in INFRA_IMPORT_ROOTS:
            domain_infra.append(f"{relative} -> {imported_module}")
        if (
            relative.startswith(PRESENTATION_PREFIXES)
            and imported_module.startswith("codes.models")
            and (relative, imported_module) not in PRESENTATION_DOMAIN_ALLOWLIST
        ):
            presentation_domain.append(f"{relative} -> {imported_module}")
        if relative.startswith("codes/services/") and root in {"dash", "flask"}:
            service_framework.append(f"{relative} -> {imported_module}")
    return domain_infra, presentation_domain, service_framework


def function_findings(
    relative: str, tree: ast.AST
) -> tuple[
    list[ast.FunctionDef | ast.AsyncFunctionDef],
    list[dict[str, int | str]],
    list[str],
    list[str],
]:
    functions = [
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    rows: list[dict[str, int | str]] = []
    excessive_parameters: list[str] = []
    boolean_flags: list[str] = []
    for node in functions:
        end = node.end_lineno or node.lineno
        parameters = len(node.args.args) + len(node.args.kwonlyargs)
        rows.append(
            {
                "path": relative,
                "name": node.name,
                "line": node.lineno,
                "lines": end - node.lineno + 1,
                "complexity": decision_complexity(node),
                "parameters": parameters,
            }
        )
        if parameters >= 8:
            excessive_parameters.append(f"{relative}:{node.lineno}:{node.name} ({parameters})")
        defaults = [*node.args.defaults, *node.args.kw_defaults]
        if any(
            isinstance(default, ast.Constant) and isinstance(default.value, bool)
            for default in defaults
            if default
        ):
            boolean_flags.append(f"{relative}:{node.lineno}:{node.name}")
    return functions, rows, excessive_parameters, boolean_flags


def mutable_global_count(tree: ast.Module) -> int:
    return sum(
        isinstance(node.value, (ast.Dict, ast.List, ast.Set))
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
    )


def build_report() -> dict[str, object]:
    file_rows: list[dict[str, int | str]] = []
    function_rows: list[dict[str, int | str]] = []
    all_functions: list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    graph: dict[str, set[str]] = {}
    domain_infra: list[str] = []
    presentation_domain: list[str] = []
    service_framework: list[str] = []
    excessive_parameters: list[str] = []
    boolean_flags: list[str] = []
    env_reads = 0
    inline_styles = 0
    mutable_globals = 0

    paths = python_paths()
    modules = {module_name(path) for path in paths}
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        relative = path.relative_to(ROOT).as_posix()
        imported = imports(tree)
        graph[module_name(path)] = imported & modules
        env_reads += source.count("os.environ")
        if relative.startswith("codes/app_modules/"):
            inline_styles += source.count("style={") + source.count("style = {")

        dependency_rows = dependency_findings(path, relative, imported)
        domain_infra.extend(dependency_rows[0])
        presentation_domain.extend(dependency_rows[1])
        service_framework.extend(dependency_rows[2])

        functions, rows, excessive, flags = function_findings(relative, tree)
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        file_rows.append(
            {
                "path": relative,
                "lines": len(source.splitlines()),
                "functions": len(functions),
                "classes": len(classes),
            }
        )
        all_functions.extend((path, node) for node in functions)
        function_rows.extend(rows)
        excessive_parameters.extend(excessive)
        boolean_flags.extend(flags)
        mutable_globals += mutable_global_count(tree)

    scss_rows = []
    for path in sorted((ROOT / "assets").rglob("*.scss")):
        source = path.read_text(encoding="utf-8")
        scss_rows.append(
            {"path": path.relative_to(ROOT).as_posix(), "lines": len(source.splitlines())}
        )

    function_rows.sort(key=lambda row: (int(row["complexity"]), int(row["lines"])), reverse=True)
    file_rows.sort(key=lambda row: int(row["lines"]), reverse=True)
    scss_rows.sort(key=lambda row: int(row["lines"]), reverse=True)
    cycles = find_cycles(graph)
    critical_cycles = [
        cycle
        for cycle in cycles
        if any(module.startswith(("codes.core", "codes.models")) for module in cycle)
    ]
    active_exceptions = []
    exception_doc = (ROOT / "docs" / "architecture-exceptions.md").read_text()
    for section in exception_doc.split("### ")[1:]:
        title = section.splitlines()[0]
        if "Status: removed" not in section:
            active_exceptions.append(title)

    return {
        "summary": {
            "python_files": len(paths),
            "python_lines": sum(int(row["lines"]) for row in file_rows),
            "test_files": len(list((ROOT / "tests").glob("test_*.py"))),
            "scss_files": len(scss_rows),
            "environment_reads": env_reads,
            "inline_style_dicts": inline_styles,
            "mutable_module_globals": mutable_globals,
            "exact_duplicate_function_groups": len(duplicate_functions(all_functions)),
            "import_cycles": len(cycles),
            "critical_import_cycles": len(critical_cycles),
            "domain_infrastructure_imports": len(domain_infra),
            "presentation_domain_imports": len(presentation_domain),
            "service_framework_imports": len(service_framework),
            "active_architecture_exceptions": len(active_exceptions),
        },
        "largest_python_files": file_rows[:25],
        "largest_scss_files": scss_rows[:15],
        "complexity_hotspots": function_rows[:30],
        "change_frequency": changed_files(),
        "excessive_parameter_functions": excessive_parameters,
        "boolean_flag_functions": boolean_flags,
        "cycles": cycles,
        "critical_cycles": critical_cycles,
        "domain_infrastructure_imports": sorted(domain_infra),
        "presentation_domain_imports": sorted(presentation_domain),
        "service_framework_imports": sorted(service_framework),
        "duplicate_function_groups": duplicate_functions(all_functions),
        "active_architecture_exceptions": active_exceptions,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if args.check:
        summary = report["summary"]
        protected = (
            "critical_import_cycles",
            "domain_infrastructure_imports",
            "presentation_domain_imports",
            "service_framework_imports",
            "active_architecture_exceptions",
        )
        failures = {key: summary[key] for key in protected if summary[key] != 0}
        if failures:
            print("Architecture migration regression: " + json.dumps(failures, sort_keys=True))
            return 1
        print("Critical migrated paths and exception register: passing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
