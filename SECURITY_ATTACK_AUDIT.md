# CenvarnLocal Security Attack Audit

**Assessment date:** 2026-07-14  
**Assessed commit:** `5929bad2` (`optimization`)  
**Target:** isolated Cenvarnprocesses on `127.0.0.1:8053` and production-mode `127.0.0.1:8054`  
**Decision:** **All identified application findings remediated; production infrastructure validation remains required**

## Scope And Safety

This was an authorized attack against the repository owner's localhost-only early-development application. No deployed site, third-party provider, real account, credential, or production database was targeted. Startup data fetching was disabled. Tests used bounded request bodies and disposable sessions; destructive account/database operations were not executed.

The audit covered source review, trust boundaries, secret patterns, SAST, Python/npm dependency advisories, production configuration behavior, authentication and private-route enforcement, CSRF, XSS output handling, SQL injection candidates, SSRF candidates, HTTP methods, security headers, host headers, path traversal, malformed parameters, oversized bodies, and concurrent unauthenticated requests.

## Executive Summary

No direct SQL injection, SSRF, reflected XSS, path traversal, private-analysis IDOR, CSRF bypass, webhook-signature bypass, metrics disclosure, or development-persona exposure in production was demonstrated. All eight application findings identified by this assessment are resolved and covered by regression tests. The unassessed deployment infrastructure listed under limitations must still be validated before launch.

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 0 open / 2 resolved |
| Medium | 0 open / 3 resolved |
| Low | 0 open / 3 resolved |

The formerly highest risks, vulnerable dependencies and unauthenticated
resource-exhaustion paths, are now enforced by the release dependency audit,
request-size limits, and durable production rate limiting.

## Findings

### SEC-001 - Resolved (formerly High) - Pinned Python Stack Contained 19 Unique Known Advisories

**Affected:** `requirements.txt`, Python runtime and security workflows

`pip-audit -r requirements.txt --strict` reported 23 records representing 19 unique package/advisory pairs across eight packages:

- Werkzeug `3.0.3`: five advisories, including multipart resource exhaustion; fixes span `3.0.6` through `3.1.6`.
- Requests `2.32.3`: credential forwarding and temporary-file issues; fixes `2.32.4`/`2.33.0`.
- python-dotenv `1.0.1`: symlink-following rewrite issue; fix `1.2.2`.
- lxml `5.2.2`: external entity/local-file disclosure under unsafe parser defaults; fix `6.1.0`.
- python-jose `3.3.0`: algorithm-confusion and JWE decompression denial-of-service advisories; partial fix `3.4.0`, with one advisory reporting no fixed version.
- cryptography `42.0.8`: five OpenSSL/certificate/EC advisories; fixes up to `48.0.1`.
- Flask `3.0.3`: session cache-variance advisory; fix `3.1.3`.
- ecdsa `0.19.2`: P-256 timing attack with no reported fixed version.

The application fixes JWT algorithms to `RS256`, does not expose a general XML upload parser, and currently emits `Vary: Cookie`; those facts reduce several individual exploit paths but do not justify retaining the vulnerable set. The Flask/Werkzeug age also directly contributes to SEC-003.

**Impact:** Known denial-of-service, authentication/cryptographic, credential, XML, cache, and path-handling weaknesses remain in the release artifact. The normal release gate can be green while the scheduled security job fails.

**Remediation:** Upgrade and repin the dependency set, remove `python-jose[cryptography]`/`ecdsa` if a maintained JWT verifier can satisfy provider requirements, run compatibility tests, and include `pip-audit --strict` in the release gate rather than only a separate scheduled workflow.

**Regression gate:** CI and `scripts/release-gate.sh` must fail on an actionable high/critical runtime advisory; document narrowly scoped suppressions with reachability evidence and expiry.

**Resolution (2026-07-14):** Flask, Werkzeug, Requests, python-dotenv, lxml,
and cryptography were upgraded to advisory-free current pins. Vulnerable
`python-jose[cryptography]` and its `ecdsa` dependency were replaced by
`PyJWT[crypto] 2.13.0`; JWKS keys now pass through `PyJWK`, and verification
remains fixed to `RS256`. A real RSA/JWKS regression test proves valid tokens
work and HS256 algorithm substitution is rejected. `pip-audit 2.10.1` is now a
pinned proof dependency and `scripts/release-gate.sh` runs
`python -m pip_audit -r requirements.txt --strict`, so ordinary PR validation
cannot pass while the dependency audit fails. Closure evidence: `No known
vulnerabilities found`; full gate `1014 passed, 2 skipped`.

### SEC-002 - Resolved (formerly High) - Public Endpoints Accepted Large Bodies And Bursts Without Throttling

**Affected:** `codes/app.py:251`, `codes/billing.py:66`, `codes/landing_pages.py:20`, `codes/app.py:162`

The Flask-Limiter instance uses `default_limits=[]`, and no Flask route is decorated with a limiter. There is no `MAX_CONTENT_LENGTH`. Live evidence:

- `/billing/webhook` accepted and fully uploaded 64 KiB, 1 MiB, and 5 MiB bodies before returning `400` for invalid signatures.
- Twenty concurrent unauthenticated 256 KiB webhook posts all reached application handling and returned `400`; none returned `413` or `429`.
- `/_dash-update-component` accepted 1 MiB and 5 MiB uploads before parsing and returning `400`.

The webhook is correctly exempt from CSRF and correctly verifies Stripe signatures, but it calls `request.get_data()` before rejection. Waitlist submissions can write/send email, and unique company-logo requests can consume database/provider capacity when configured, yet neither has route-level abuse controls.

**Impact:** A remote unauthenticated attacker can consume worker time, memory, bandwidth, database capacity, SMTP quota, or logo-provider quota. A sync Gunicorn worker is especially easy to occupy with concurrent slow/large bodies.

**Remediation:** Set an application and reverse-proxy request-body limit; use a tighter webhook-specific limit compatible with Stripe; apply Redis-backed per-IP and per-identity limits to webhook, waitlist, logo, billing, auth, and Dash callback routes; enforce request timeouts/concurrency limits at the proxy; alert on `413`/`429` and abuse rates.

**Regression gate:** Oversized requests must return `413` before route logic, and bursts must produce deterministic `429` responses without provider/database calls.

**Resolution (2026-07-14):** The application now enforces a 2 MiB global
request limit and a 256 KiB Stripe webhook limit before signature handling.
Flask-Limiter has a shared production-backed default limit plus stricter limits
for Dash callbacks, webhooks, waitlist, logo, billing, and development-persona
routes. Exact `413` and `429` handlers preserve security semantics. Regression
tests prove oversized requests never reach webhook verification and a sixth
waitlist request returns `429` before persistence. Closure evidence: focused
suite `55 passed, 2 skipped`; full gate `1017 passed, 2 skipped`.

### SEC-003 - Resolved (formerly Medium) - Configured Trusted Hosts Were Not Enforced

**Affected:** `codes/app.py:51`, `codes/core/production_readiness.py`

The application sets `server.config["TRUSTED_HOSTS"]`, but the pinned Flask `3.0.3` does not enforce the modern trusted-host behavior expected by this configuration. A production-mode instance configured with `TRUSTED_HOSTS=127.0.0.1,localhost` returned `200` for `Host: attacker.invalid`.

`PUBLIC_BASE_URL` prevents the tested sitemap from reflecting the hostile host when correctly configured, but accepting arbitrary hosts still weakens origin assumptions, absolute URL generation, proxy handling, and future password/OAuth flows. A same-origin CSRF comparison is not a trusted-host check.

**Remediation:** Upgrade Flask/Werkzeug to versions that enforce trusted hosts, add explicit early host rejection as defense in depth, configure the edge proxy allowlist, and test hosts with ports, case, trailing dots, IPv6, and forwarded-host headers.

**Regression gate:** Unknown `Host` and untrusted forwarded host values return `400` before session or route processing in production mode.

**Resolution (2026-07-14):** Flask/Werkzeug were upgraded to versions that
enforce `TRUSTED_HOSTS`, and the app now invokes native host validation in its
first request hook before authentication, CSRF, or session mutation. Regression
tests prove an unknown host returns `400` without a session cookie while a
configured host with a port remains valid. Closure evidence: focused suite
`36 passed, 2 skipped`; full gate `1019 passed, 2 skipped`.

### SEC-004 - Resolved (formerly Medium) - JWT Issuer And Audience Validation Was Incomplete

**Affected:** `codes/auth.py:121`, `codes/auth.py:203`, `codes/auth.py:221`

Auth0 validates fixed `RS256`, audience, and issuer. Clerk explicitly disables audience validation and supplies no issuer. Supabase calls `_decode_jwt` with both audience and issuer set to `None`, disabling audience validation and omitting issuer validation. Signature verification remains present, so arbitrary unsigned tokens were not accepted; the risk is token confusion across contexts that share trusted signing material.

**Impact:** A valid token minted for a different audience or context may be accepted as an application session if it is signed by a trusted provider key and contains a usable subject.

**Remediation:** Require provider-specific issuer and audience values, validate token type/authorized party where applicable, require `exp`/`iat`/`nbf` semantics, and add negative tests using correctly signed tokens with wrong issuer, audience, and token purpose.

**Resolution (2026-07-14):** Clerk now requires and validates explicit issuer
and audience configuration. Supabase validates its project-specific auth issuer
and configured JWT audience (`authenticated` by default). Production preflight
rejects incomplete Clerk claim context. Real signed-token tests prove valid
RS256 tokens pass while wrong algorithm, issuer, and audience fail. Closure
evidence: focused suite `16 passed`; full gate `1021 passed, 2 skipped`.

### SEC-005 - Resolved (formerly Medium) - CSP Relied On Executable `unsafe-inline`

**Affected:** `codes/security.py:295`

The live response includes `script-src 'self' 'unsafe-inline'` and `style-src 'self' 'unsafe-inline'`. Output-escaping probes did not produce reflected XSS, and `object-src`, `base-uri`, and `frame-ancestors` are restrictive. Nevertheless, inline script permission removes a major containment layer if a future template or component introduces an injection sink.

**Remediation:** Move inline boot scripts to static assets or use per-response nonces/hashes, remove `unsafe-inline` from `script-src`, and evaluate style nonces/hashes separately. Add CSP reporting during rollout.

**Resolution (2026-07-14):** The security middleware now hashes every nonempty
inline script in each HTML response and emits those exact CSP hashes. Executable
`script-src 'unsafe-inline'` is removed. Stylesheets are restricted to self and
Google Fonts; the remaining `style-src-attr 'unsafe-inline'` is narrowly scoped
to Dash's generated style attributes rather than permitting inline executable
scripts or style elements. Regression tests verify every inline script hash.
The live Firefox desktop/tablet/mobile, light/dark, and 200%-zoom matrix loaded
and operated with zero accessibility violations or overflow. Closure evidence:
focused suite `34 passed, 2 skipped`; full gate `1022 passed, 2 skipped`.

### SEC-006 - Resolved (formerly Low) - Unauthenticated Account Deletion Returned 500

**Affected:** `codes/app.py:187`, `codes/app_modules/session.py:22`

In production mode, `POST /account/delete` with a valid same-origin header and no authenticated session raises `RuntimeError` from `get_user_id()` and returns `500`. No deletion occurred because failure precedes database access.

**Impact:** Incorrect security semantics, noisy error telemetry, and a cheap error-generation path.

**Remediation:** Apply `@require_auth` or translate missing authentication to `401` before any deletion work. Add unauthenticated, wrong-user, expired-session, and successful-erasure route tests.

**Resolution (2026-07-14):** `/account/delete` now requires authentication at
the route boundary before user resolution or database access. Regression tests
prove unauthenticated requests return `401` with zero deletion calls and the
authenticated multi-store erasure flow still returns its deletion summary.
Closure evidence: focused suite `8 passed`; full gate `1024 passed, 2 skipped`.

### SEC-007 - Resolved (formerly Low) - Unsupported Methods Are Misreported As Server Errors

**Affected:** `codes/error_pages.py:56`

`TRACE /` and `CONNECT /` returned `500`. Werkzeug raises an HTTP `405`, but `_render_error` maps every HTTP status absent from `ERROR_PAGE_COPY` to `500`.

**Impact:** False server-error alerts and inaccurate client behavior; this did not enable TRACE reflection.

**Remediation:** Preserve the original safe HTTP status for untemplated `4xx` responses, add a generic `405` page, and reject unsupported methods at the edge.

**Resolution (2026-07-14):** The shared error renderer now preserves the
original HTTP status for errors without a branded template and emits only the
standard status phrase, preventing exception-detail disclosure. Regression
tests prove `TRACE` and `CONNECT` remain `405`, and an untemplated `418` remains
`418` without exposing its internal description. Closure evidence: focused
suite `9 passed`; full gate `1026 passed, 2 skipped`.

### SEC-008 - Resolved (formerly Low) - Access Tokens Are Copied Into Client-Side Session Cookies

**Affected:** `codes/auth.py:343`

`set_authenticated_user` writes `_auth_token` into Flask's signed but unencrypted client-side session. `HttpOnly`, `Secure`, and `SameSite=Lax` were confirmed in production mode, but signing protects integrity, not confidentiality.

**Impact:** Tokens are duplicated into every session-cookie request and may be exposed through cookie capture, size limits, diagnostics, or tooling. A stolen session already has impact, but duplicating bearer material increases blast radius and operational leakage risk.

**Remediation:** Store only an opaque server-side session identifier or minimal nonsecret claims in the cookie. Keep provider tokens in an encrypted server-side session/token store with bounded lifetime and revocation.

**Resolution (2026-07-14):** Bearer and Auth0 callback authentication now
store only the verified nonsecret user ID in the signed client session. Provider
tokens exist only for immediate verification and are never serialized into the
cookie; logout still removes the legacy `_auth_token` key from existing
sessions. Regression tests cover bearer authentication, OAuth callback storage,
and legacy cleanup. Closure evidence: focused suite `6 passed`; full gate
`1028 passed, 2 skipped`.

## Controls That Resisted Attack

- Missing or incorrect internal metrics tokens returned `404`.
- Missing and hostile CSRF origins returned `403`; correct localhost origin returned `200`.
- Stripe webhook bodies without valid signatures returned `400` and did not update subscriptions.
- Development impersonation returned `404` in production mode.
- Unauthenticated private custom analysis returned `401`; source review confirms owner-scoped snapshot lookup.
- Session cookies in production were `Secure`, `HttpOnly`, and `SameSite=Lax`; HSTS was present.
- Security headers included nosniff, frame denial, restrictive permissions, opener/resource policy, and CSP.
- Asset path traversal returned `404`.
- Logo fallback escaped hostile symbol text; provider destination is fixed to `https://img.logo.dev`, so Bandit's generic URL-open warning is not SSRF.
- Bandit SQL warnings use fixed table names or explicit column allowlists/parameterized values; no SQL injection was confirmed.
- npm audit reported zero vulnerabilities.
- Secret-pattern scanning of tracked non-test/non-documentation files found no recognized private keys, provider tokens, or credential-bearing database URLs.
- Focused security/auth/billing/privacy/logo suite passed: `50 passed, 2 skipped`.

## Tool Results And Limitations

- Bandit scanned 24,138 lines: zero high-severity findings, seven medium scanner findings, and 17 low findings. The reported SQL and URL-open candidates were manually reviewed as mitigated; the all-interface bind is intentional only in production deployment.
- `pip-audit` used the current advisory database on the assessment date. Advisory applicability varies, but the dependency gate fails regardless.
- This was black-box and source-assisted localhost testing, not an external penetration test. No reverse proxy, TLS terminator, cloud IAM, managed database, Redis deployment, Auth0/Clerk/Supabase tenant, Stripe account, SMTP provider, DNS, container, or host operating system was assessed.
- No real screen-reader/manual accessibility, production-scale slow-client attack, multi-worker race exploit, external callback, social engineering, persistence, or destructive data test was performed.

## Closure Status

SEC-001 through SEC-008 were remediated in order, independently tested, and
committed. The final application gate passed `1028` tests with `2` intentional
skips, the combined SEC regression suite passed `20` tests, and the strict
dependency audit reported no known vulnerabilities.
Proxy-backed slow-body/load testing and external infrastructure assessment
remain deployment gates rather than open source-code findings.
