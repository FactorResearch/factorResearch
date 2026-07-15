# Production Ownership

## Interim Assignments

Until additional operators are named, the repository owner is the accountable and escalation owner. One person may hold multiple roles before launch, but public certification requires a second reviewer for security and release approval.

| Area | Accountable role | Interim owner | Required independent approval |
|---|---|---|---|
| Application and release | Engineering owner | Amin | Release reviewer |
| Infrastructure and availability | Operations owner | Amin | Engineering reviewer |
| PostgreSQL and Redis | Data-platform owner | Amin | Operations reviewer |
| Application security | Security owner | Amin | Independent security assessor |
| Privacy and retention | Privacy owner | Amin | Legal/privacy reviewer |
| Financial-model integrity | Quantitative-model owner | Amin | Independent model reviewer |
| Billing and subscriptions | Payments owner | Amin | Engineering reviewer |
| Incident command | On-call incident commander | Amin | Backup commander required pre-launch |

## Responsibilities

- Engineering owns correctness, test gates, dependency health, and rollback readiness.
- Operations owns capacity, observability, backups, recovery, and incident coordination.
- Security owns threat models, vulnerability disposition, access review, and penetration-test closure.
- Privacy owns data inventory, consent, retention, deletion, and vendor processing records.
- Model integrity owns source provenance, golden calculations, model versions, and bias disclosure.
- Payments owns webhook integrity, subscription reconciliation, and Stripe incident response.

## Decision Rules

- Critical/high security findings, failed restore drills, unresolved cross-user isolation defects, or red release gates cannot be accepted by the implementation author alone.
- Every risk acceptance names an owner and expiration date.
- The incident commander may disable analysis, billing, providers, or public visibility without prior approval to protect users or data.
- Production access is least privilege, individually assigned, logged, reviewed monthly, and never shared.

## Escalation

1. Page the active incident commander for availability, security, privacy, payment, or data-integrity events.
2. Engage the relevant accountable owner within five minutes for severity 1 and fifteen minutes for severity 2.
3. Engage hosting, Auth0, Stripe, database, Redis, or market-data vendors using their recorded support channel.
4. Engage legal/privacy review when personal data, notification duties, or license restrictions may be involved.
