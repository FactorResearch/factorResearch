# ISSUE_145 direct dependency inventory

## Contract

`pyproject.toml` and `package.json` are the only hand-edited direct dependency
declarations. Their lockfiles contain exact transitive resolutions. Every direct
declaration must appear below with an owner and a disposition:

- **Keep:** approved and owned for the current architecture.
- **Temporary:** required by a legacy product path and removed by a named
  migration.
- **Replace:** retained only until the named maintained replacement is adopted.
- **Prohibited:** must not be introduced without an accepted exception ADR and
  explicit user approval.

All shipped direct packages have permissive or approved weak-copyleft licenses.
The dependency-review gate blocks newly introduced high-severity
vulnerabilities and prohibited licenses. Legal approval remains a human release
responsibility; scanner output is inventory evidence, not legal advice.

## Python runtime dependencies

| Package | Owner | Disposition | License posture | Purpose and boundary | Upgrade/removal rule |
|---|---|---|---|---|---|
| Dash | Customer UI | Temporary | MIT | Legacy customer and internal Dash presentation | Remove customer use under ISSUE_142; retain only approved internal tooling |
| Plotly | Customer UI | Temporary | MIT | Charts on retained Dash pages | Replace customer charts under ISSUE_142; keep internal compatibility tested |
| pandas | Quant Platform | Temporary | BSD-3-Clause | Existing table and time-series paths | Narrow after Polars/Arrow owning issues; never rewrite DataFrame infrastructure |
| NumPy | Quant Platform | Keep | BSD-3-Clause and bundled permissive notices | Numeric arrays and financial kernels | Keep within a tested major; use Rust only after benchmark/parity gate |
| Requests | Data Platform | Replace | Apache-2.0 | Existing provider and authentication HTTP paths | New transports use shared HTTPX only when an owning issue migrates callers |
| python-dotenv | Platform Engineering | Temporary | BSD-3-Clause | Local-development environment loading | Remove from production paths when typed configuration/secret management owns startup |
| Gunicorn | Runtime Platform | Temporary | MIT | Legacy Flask/Dash WSGI process serving | Replace only with the approved ASGI runtime under ISSUE_152/141 |
| Jinja2 | Customer Communications | Keep | BSD-3-Clause | Sandboxed email-template rendering through a maintained engine | Keep templates autoescaped; never build a template engine |
| lxml | Data Platform | Keep | BSD-style | Maintained HTML/XML parsing compatibility | Keep behind provider normalization; never build a parser replacement |
| finnhub-python | Data Platform | Replace | Apache-2.0 | Legacy Finnhub provider SDK | Narrow behind shared maintained HTTP transport in the provider migration |
| Psycopg | Data Platform | Keep | LGPL-3.0-only | PostgreSQL driver | Keep; database access remains behind repositories |
| PyJWT | Security Engineering | Keep | MIT | JWT primitives | Keep behind authentication boundary; never implement JWT primitives |
| Flask-Limiter | Security Engineering | Temporary | MIT | Legacy Flask route throttling | Replace only with the approved API/runtime control under migration |
| redis | Runtime Platform | Keep | MIT | Maintained Redis/Valkey-compatible Python client | Keep client; evaluate server migration separately without building RESP |
| cryptography | Security Engineering | Keep | Apache-2.0 OR BSD-3-Clause | Encryption and signature primitives | Keep; never implement cryptographic primitives |
| MarkupSafe | Customer UI | Temporary | BSD-3-Clause | Safe legacy Flask/Dash markup handling | Leaves with legacy presentation stack where no direct use remains |
| Werkzeug | Customer UI | Temporary | BSD-3-Clause | Legacy Flask HTTP utilities | Leaves with legacy Flask control plane |
| Flask | Customer UI | Temporary | BSD-3-Clause | Legacy WSGI routes and Dash server | Customer control plane migrates under ISSUE_141/142 |
| Stripe | Billing | Keep | MIT | Official billing SDK | Keep official SDK, pinned API version, webhook fixtures, and major rollback range |

## Python development and supply-chain dependencies

| Package | Owner | Disposition | License posture | Purpose and boundary | Upgrade/removal rule |
|---|---|---|---|---|---|
| Bandit | Security Engineering | Keep | Apache-2.0 | Maintained Python SAST | Review major upgrades against configured severity gate |
| coverage | Quality Engineering | Keep | Apache-2.0 | Test coverage evidence | Diagnostic only; never substitute percentage for correctness |
| cyclonedx-bom | Security Engineering | Keep | Apache-2.0 | Maintained Python CycloneDX SBOM generator | Keep output contract compatible with release archive |
| Hypothesis | Quant Platform | Keep | MPL-2.0 | Property tests for invariants and round trips | Add tests through owning financial/schema issues |
| Locust | Performance Engineering | Keep | MIT | Production-shaped load test client | Keep outside application runtime |
| mypy | Platform Engineering | Keep | MIT | Strict Python boundary typing | Expand protected files incrementally |
| pip-audit | Security Engineering | Keep | Apache-2.0 | Python advisory scanner | Keep strict and block unresolved advisories without recorded exception |
| pytest | Quality Engineering | Keep | MIT | Python test runner | Explicitly declared; never install out of band in CI |
| PyYAML | API Platform | Keep | MIT | Parse checked-in OpenAPI contracts in the compatibility gate | Keep outside request handling; never build a YAML parser |
| Ruff | Platform Engineering | Keep | MIT | Python lint and format enforcement | Expand protected files incrementally |

## Node development dependencies

| Package | Owner | Disposition | License posture | Purpose and boundary | Upgrade/removal rule |
|---|---|---|---|---|---|
| axe-core | Accessibility | Keep | MPL-2.0 | Maintained accessibility engine loaded by the repository's Selenium audit scripts | Keep WCAG audit fixtures compatible; avoid unused browser-driver CLI wrappers |
| Sass | Design System | Temporary | MIT | Compile the current SCSS source of truth | Retain through frontend migration; address deprecations before behavior changes |

## Rust and native dependency budget

The repository has no `Cargo.toml`, `Cargo.lock`, native dependency, Rust wheel,
or Rust compile step. The current native dependency budget and compile time are
therefore exactly zero. The first owning native issue must document each crate,
commit `Cargo.lock`, run cargo-audit and cargo-deny, test Python fallback/parity,
and establish a measured compile-time budget. ISSUE_145 does not create a
placeholder native package.

## Approved license policy and exceptions

Current direct licenses are MIT, BSD-3-Clause/BSD-style, Apache-2.0,
LGPL-3.0-only (Psycopg), or MPL-2.0 (Hypothesis and axe). Dependency review
rejects AGPL-3.0, GPL-3.0, SSPL-1.0, and BUSL-1.1 introductions. Any exception
must record the dependency, owner, business reason, exact license/advisory,
expiry, compensating controls, and removal trigger in the issue and PR.
