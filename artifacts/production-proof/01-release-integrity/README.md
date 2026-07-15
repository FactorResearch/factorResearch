# Phase 1 Release Integrity Evidence

**Status:** Automated controls and local consecutive-run proof complete; hosted artifact evidence remains open.
**Evidence date:** 2026-07-14

## Implemented Controls

- `.github/workflows/pr-tests.yml` runs the repository release gate on every pull request to `main`.
- `scripts/release-gate.sh` compiles Python, imports the app without startup side effects, validates JavaScript syntax, compiles SCSS, compares tracked generated CSS, runs the full test suite, and checks the diff.
- Tests reject accidental external network access by default; explicitly approved live tests require `@pytest.mark.live_network`.
- `scripts/check-production-config.py` validates required production controls and configuration relationships without printing values.
- Security workflows perform secret, dependency, SAST, npm, and SBOM checks.

## Open Certification Evidence

- [x] Record 20 consecutive non-flaky release-gate runs.
- [ ] Add supported-browser smoke execution once Phase 10 infrastructure exists.
- [ ] Record PostgreSQL/Redis integration runs against production-supported versions.
- [ ] Define and enforce branch/critical-module coverage thresholds after measuring the baseline.
- [ ] Archive the immutable production artifact, checksum, dependency lock state, and SBOM.
- [ ] Confirm the production preflight passes using deployment secrets without exposing values.

## Local Gate

```bash
./scripts/release-gate.sh
```

Production configuration validation runs only in an environment populated by the deployment secret manager:

```bash
PYTHONPATH=. python scripts/check-production-config.py
```
