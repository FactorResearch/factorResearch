#!/usr/bin/env python3
"""Detect exact duplicated non-trivial function bodies in protected modules."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ROOT / "codes" / "core",
    ROOT / "codes" / "composition.py",
    ROOT / "codes" / "app_modules" / "composition.py",
)
MIN_AST_NODES = 18


def paths() -> list[Path]:
    found: list[Path] = []
    for target in TARGETS:
        found.extend(target.rglob("*.py") if target.is_dir() else [target])
    return sorted(found)


def main() -> int:
    bodies: dict[str, list[str]] = defaultdict(list)
    for path in paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = node.body[1:] if ast.get_docstring(node) else node.body
            body_size = sum(1 for statement in body for _ in ast.walk(statement))
            if body_size < MIN_AST_NODES:
                continue
            fingerprint = ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)
            location = f"{path.relative_to(ROOT)}:{node.lineno}:{node.name}"
            bodies[fingerprint].append(location)

    duplicates = [locations for locations in bodies.values() if len(locations) > 1]
    if duplicates:
        print("Structural duplication gate failed:")
        for locations in duplicates:
            print("- " + ", ".join(locations))
        return 1
    print("Protected-layer structural duplication: passing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
