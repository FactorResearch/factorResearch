# Purpose
Define a predictable reviewable workflow for every code change.
# Branches and commits
- Use descriptive issue-linked branch names.
- Commits must be focused and explain intent.
- Do not mix unrelated refactoring with feature or bug work.
- Never commit secrets, generated junk, or local configuration.
# Pull request contract
Every PR must state:
- Problem and customer impact.
- Scope and non-goals.
- Design or issue reference.
- What changed.
- Testing performed.
- Failure and rollback behavior.
- Database, API, security, performance, and observability impact.
- Screenshots for visible UI changes.
- Migration and deployment steps.
# Review rules
- Prefer small, understandable PRs.
- Material changes require independent review.
- Reviewers must examine correctness, architecture, contracts, security, tests, operations, and maintainability.
- Approval is not valid when the reviewer cannot explain the change.
# Merge and completion
Required checks must pass. Documentation, tests, migrations, flags, monitoring, and cleanup tasks must be complete or explicitly tracked.
# AI implementation requirements
The AI must preserve scope, avoid opportunistic rewrites, and produce a review summary matching the actual diff.
