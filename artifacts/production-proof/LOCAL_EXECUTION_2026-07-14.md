# Local Production-Proof Execution

**Date:** 2026-07-14  
**Branch:** `optimization`  
**Scope:** Locally executable controls only. This record does not certify public production launch.

## Passed Evidence

| Control | Result |
|---|---|
| Complete release gate | `1028 passed, 2 skipped`; dependency audit clean; generated CSS deterministic |
| Flake proof | 20 consecutive complete release-gate runs passed on the unchanged candidate |
| Focused reliability/model/privacy/deployment matrix | `51 passed` |
| Focused security matrix after SAST correction | `35 passed, 2 skipped` |
| Python dependency audit | No known vulnerabilities |
| npm production dependency audit | 0 vulnerabilities |
| SAST release threshold | 0 medium/high Bandit findings after narrow reviewed suppressions |
| SBOM | Python and npm CycloneDX documents generated under `05-security/` |
| Live accessibility | 19 Firefox scenarios; 0 axe violations; 0 horizontal overflow |
| Local baseline load | 1 user, 16 evaluated requests, 0 failures, p95 9 ms |
| Local expected-peak probe | 10 users, 172 evaluated requests, 0 failures, p95 20 ms |
| Local instant-spike probe | 30 users, 512 evaluated requests, 0 failures, p95 110 ms |
| Process model | Gunicorn 22.0.0 with 2 sync workers |
| Configured database reachability | Users, market, and analytics stores each passed read-only `SELECT 1` |

The load probes exercised screener, legal pages, and public analyze-page reads.
They prove the harness, routing, and local two-worker behavior, not cold provider
analysis, authenticated portfolio simulation, Redis, or production capacity.

## Corrected Locally

- Security CI now blocks medium/high Bandit findings and separately reports low
  hygiene findings. Narrow `nosec` annotations document fixed table names,
  allowlisted sort columns, static SQL fragments, the fixed logo-provider host,
  and intentional production ingress binding.
- Root npm metadata now has an explicit package name, version, and private flag,
  allowing a valid npm CycloneDX SBOM to be generated.
- Sass mixed-declaration deprecations were resolved without changing layout
  semantics; the final SCSS build and release gate are warning-free.

## Local Blockers Observed

The configured production preflight failed closed because the local environment
does not define `TRUSTED_HOSTS`, `REDIS_URL`, `SEC_USER_AGENT`, a valid Fernet
`ENCRYPTION_KEY`, or an HTTPS public base URL. Values were not fabricated.

No local PostgreSQL server, Redis server, container runtime, Chromium/WebKit
driver, reverse proxy, TLS endpoint, or disposable restore target was available.
Therefore the following cannot be proved by this machine as currently
configured:

- Redis-backed multi-worker integration and Redis outage/recovery behavior.
- Full encrypted backup restore, migration rollback, or measured RPO/RTO on a
  disposable production-size database.
- TLS, trusted-proxy, DNS, IAM, secret-manager, and edge body/timeout controls.
- Chromium/WebKit, physical-device, screen-reader, and human keyboard review.
- Cold provider quota/latency, Auth0 tenant, Stripe webhook, SMTP delivery, and
  authenticated multi-user capacity behavior.
- External penetration testing, legal/privacy/licensing approval, on-call drills,
  regional recovery, canary promotion, and rollback in hosted infrastructure.

## Decision

All repository-controlled and currently executable local gates passed after the
documented corrections. Public production launch remains blocked on the
production-equivalent and independent evidence above.
