# Persistent engineering rules

## Ponytail is always on

For every coding task in this repository, apply **Ponytail Full** from
`.codex/ponytail/SKILL.md`. It remains active unless the user explicitly says
`stop ponytail` or `normal mode`.

After understanding the affected flow, stop at the first solution that works:

1. Skip speculative work (YAGNI).
2. Reuse code and patterns already in the repository.
3. Prefer the standard library, then native platform features, then an existing
   dependency.
4. Add only the minimum code required for the accepted behavior.

Prefer deletion over addition and the smallest correct root-cause diff over new
abstractions, dependencies, configuration, scaffolding, or flexibility for
hypothetical future needs. Do not simplify away security, validation, error
handling that prevents data loss, accessibility, tests for non-trivial logic, or
anything explicitly required.

Before declaring work complete, review the diff for dead code, duplication,
unused flexibility, unnecessary files, and avoidable boilerplate. Remove it when
safe. Mark any deliberate shortcut with `ponytail: <ceiling>, <upgrade trigger>`.
