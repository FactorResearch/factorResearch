# Development Workflow

This repository uses `main` as the shared integration branch. Keep `main`
deployable, and keep unreleased markets disabled in `feature_flags.json`.

## Before Starting Work

1. Confirm the work does not already exist in `roadMap.md` or another active
   branch.
2. Agree on the implementation scope before changing product behavior.
3. Update local `main` with a fast-forward-only pull:

   ```bash
   git switch main
   git pull --ff-only
   ```

4. Create the branch from the updated `main`:

   ```bash
   git switch -c <branch-name>
   ```

## Branch Types

- `main`: shared infrastructure and completed integrations. It must remain
  deployable; unreleased features stay disabled behind flags.
- Country branches: lowercase country name, created directly from `main`, for
  example `canada` or `uk`. They contain only that market's adapter, ingestion,
  tests, documentation, assets, and flag entry. Every country branch must add
  and maintain a unique `README_<COUNTRY>.md` publication runbook before it can
  be merged or considered for launch. The runbook must cover market-specific
  source rights, population commands, acceptance criteria, release blockers,
  evidence, enablement steps, and the user-facing release boundary.
- Version branches: exact lowercase release name, for example `v2.2` or `v3`.
  Treat a published version branch as shared history.
- Short-lived work branches: use a descriptive name and delete them after they
  are merged or intentionally abandoned.

Do not create branch names that differ only by letter case. Git and common file
systems handle case differently, making names such as `V2.0` and `v2.0`
operationally ambiguous.

## Shared Changes

Implement cross-market fixes once on `main`, then merge `main` into active
country branches. Do not copy or independently recreate the same fix in each
country branch.

```bash
git switch <country-branch>
git merge main
```

Rebase only unpublished local work. Never rebase or force-push `main`, a shared
country branch, or a published version branch.

## Pull Requests

Open a pull request to integrate work into `main`. Before merging:

1. Confirm the diff contains only the intended release or market scope.
2. Require the pull-request validation workflow to pass.
3. Resolve review comments and test failures.
4. Prefer a normal merge when preserving release history matters; use squash
   only for disposable work branches.
5. Delete merged short-lived branches.

For a country branch, also verify its `README_<COUNTRY>.md` matches the actual
implementation and lists every unresolved gate before requesting release
approval. A generic repository README or release-note file is not a substitute.

Configure the GitHub `main` branch protection rule to require pull requests,
one approval, resolved conversations, and the `PR validation / tests` status
check. Disable force pushes and branch deletion.

## Releases

Branches are development history; annotated tags identify immutable releases.
After release approval and verification, tag the exact approved commit:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

Do not move or reuse a published release tag. Record user-facing changes in the
branch release notes before tagging.

## Local Git Safety

Use fast-forward-only pulls so `git pull` cannot create an accidental merge:

```bash
git config pull.ff only
```

If a pull cannot fast-forward, stop and inspect the branch graph before merging
or rebasing. Never use destructive history commands to make branches appear
clean.
