# Purpose

Control third-party risk, maintenance burden, security exposure, licensing, and unnecessary complexity.

# Approval criteria

Before adding a dependency, document:

- Problem it solves.
- Why existing project code or platform capability is insufficient.
- Maintenance activity and community health.
- License compatibility.
- Security history.
- Runtime, bundle, storage, and build impact.
- Transitive dependencies.
- Replacement or removal strategy.

# Version management

- Use lockfiles.
- Pin or constrain versions intentionally.
- Automate vulnerability and outdated-package scanning.
- Test upgrades before merge.
- Avoid unmaintained packages for critical paths.

# Architectural boundaries

Wrap critical vendors behind project-owned interfaces when replacement cost or coupling is significant.

# Prohibited behavior

- Adding packages for trivial helpers without justification.
- Importing multiple libraries for the same responsibility.
- Depending on undocumented internals.
- Ignoring license restrictions.

# AI implementation requirements

The AI must search existing dependencies and utilities before proposing a new package.