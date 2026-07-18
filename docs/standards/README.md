# Cenvarn standards index

This repository mirrors the current Notion standards. Notion is the detailed
source of truth; these files are the execution layer loaded by coding agents and
CI.

## Always load

- `AGENTS.md`
- `AI_CONTEXT.md`
- `docs/engineering.md`
- `docs/testing.md`
- `docs/security.md`
- `docs/git.md`

## Load by affected layer

- UI or SCSS: `docs/frontend.md`, `docs/accessibility.md`, and the current
  `design/` mirrors.
- API: `docs/api.md`.
- Database: `docs/database.md`.
- External data: `docs/data-providers.md` and `docs/caching.md` when cached.
- Workers: `docs/workers.md` and `docs/config.md`.
- Financial calculations: `docs/financial.md`.
- Production or deployment: `docs/release.md` and `docs/log.md`.
- Dependencies: `docs/dependency.md`.

## Synchronization rule

When a Notion standard changes, update the applicable local mirror, this index,
and any mechanical enforcement in the same change. A disagreement between the
Notion source and repository mirror blocks completion.

Last reviewed: 2026-07-18.
