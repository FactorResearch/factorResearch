# Incident Severity Matrix

| Severity | Examples | Declare | Acknowledge | Update cadence | Required roles |
|---|---|---:|---:|---:|---|
| SEV-1 | cross-user exposure, active compromise, material data corruption, total outage, incorrect billing at scale | immediate | 5 minutes | 15 minutes | incident commander, operations, security/privacy or payments, communications, scribe |
| SEV-2 | major workflow unavailable, sustained SLO burn, provider failure without safe fallback, delayed billing | 10 minutes | 10 minutes | 30 minutes | incident commander, service owner, operations, scribe |
| SEV-3 | limited degradation, isolated incorrect result, recoverable backlog | 30 minutes | 30 minutes | 60 minutes | service owner, operations |
| SEV-4 | cosmetic or low-risk defect with workaround | next business day | next business day | as agreed | service owner |

The incident commander may freeze releases, disable features/providers/billing, enter maintenance or read-only mode, revoke credentials, and reduce traffic. Only the incident commander closes an incident after monitoring and synthetic journeys prove recovery. Security/privacy/legal determines notification obligations; engineers do not delay containment while waiting for attribution.
