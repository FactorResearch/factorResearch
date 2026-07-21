# Cenvarn engineering standards index

This directory indexes the repository mirrors of Cenvarn's canonical Notion
standards. Notion is the detailed human-readable source of truth; repository
instructions and CI are the execution layer. A disagreement between them is a
blocking documentation defect.

| Standard | Repository mirror | Canonical source | Version | Owner | Enforcement |
|---|---|---|---|---|---|
| AI engineering instructions | [`AGENTS.md`](../../AGENTS.md) and [`AI_CONTEXT.md`](../../AI_CONTEXT.md) | [Repository AGENTS.md — Canonical Template](https://app.notion.com/p/3a04ef32c9f781a4a795d5ac8d65d9d3) | 2026-07-20 | Platform Engineering | Agent startup and review |
| Build vs. buy and no reinvention | [`Build-vs-Buy-and-No-Reinvention-Policy.md`](../../Build-vs-Buy-and-No-Reinvention-Policy.md) | [Canonical policy](https://app.notion.com/p/3a34ef32c9f78126ba2bd57c1f050a2e) | 2026-07-20 | Architecture | `AGENTS.md`, pull-request review, and architecture exception gate |
| Engineering code standards | [`docs/engineering.md`](../engineering.md) | [Canonical standard](https://app.notion.com/p/3a04ef32c9f7816cb2a0dd105f3b2ca4) | 2026-07-17 | Platform Engineering | Quality and release gates |
| Dependency and package standards | [`docs/dependency.md`](../dependency.md) and [`docs/issue-145-dependency-inventory.md`](../issue-145-dependency-inventory.md) | [Canonical standard](https://app.notion.com/p/3a04ef32c9f781dda11ef0cc09671bbd) | 2026-07-20 | Platform Engineering | Frozen lockfiles, audits, SBOMs, dependency review, and updater |
| Testing engineering standards | [`docs/testing.md`](../testing.md) | [Canonical standard](https://app.notion.com/p/3a04ef32c9f78104b583c9f8857af541) | 2026-07-17 | Quality Engineering | Release gate and CI tests |
| Security engineering standards | [`docs/security.md`](../security.md) | Canonical Notion security standard | 2026-07-17 | Security Engineering | Security audit and dependency review |
| Git and pull-request standards | [`docs/git.md`](../git.md) | Canonical Notion Git standard | 2026-07-17 | Platform Engineering | Pull-request template and branch protection |

When a canonical standard changes, update its repository mirrors, this version
and review date, and every mechanical check affected by the rule in the same
change.
