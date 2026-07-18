# Purpose
Make security, privacy, authorization, and tenant isolation default implementation requirements.
# Core principles
- Deny by default.
- Apply least privilege.
- Treat every client input and external payload as untrusted.
- Security controls must be enforced server-side.
- Never rely on obscurity or UI hiding for authorization.
# Required controls
- Centralized authentication and session handling.
- Explicit resource-level authorization.
- Strict isolation of each user's portfolios, analyses, preferences, exports, and billing data.
- Parameterized database access.
- Output encoding and protection against cross-site scripting.
- CSRF protection where applicable.
- Rate limiting and abuse prevention.
- Secure secret storage and rotation.
- Encryption in transit and at rest where appropriate.
- Dependency, container, and secret scanning.
# Sensitive data
- Classify personal, financial, credential, billing, and operational data.
- Collect and retain only what is needed.
- Never log secrets, tokens, passwords, full payment data, or unnecessary user data.
- Define deletion and retention behavior.
# Security review
Every feature must document:
- Data handled.
- Trust boundaries.
- Authorization model.
- Abuse cases.
- Logging exposure.
- Rate-limit requirements.
- Security tests.
# Incident readiness
Security events require auditability, containment procedures, credential rotation capability, and a documented incident path.
# AI implementation requirements
Before writing security-sensitive code, the AI must identify assets, actors, trust boundaries, authorization checks, abuse paths, and required tests.
