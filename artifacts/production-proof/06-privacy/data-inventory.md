# Personal Data Inventory

| Data | Purpose | Store/vendor | Authority | Retention/deletion |
|---|---|---|---|---|
| Authenticated user ID | identity and tenant isolation | session, user DB, Auth0 | Auth0/account | cleared on account deletion; provider deletion separately requested |
| Portfolio names/holdings | user investment workspace | encrypted cache/user context | user | deleted immediately by `/account/delete` |
| Custom model snapshots | private research history | analytics/snapshot DB | user | deleted immediately by `/account/delete` |
| Subscription/customer IDs | entitlement and billing support | user DB, Stripe | Stripe | local metadata deleted; Stripe retention follows legal/payment policy |
| Usage counters | limits and abuse prevention | user DB | application | deleted immediately by `/account/delete` |
| Product analytics events | product improvement | analytics DB, optional vendors | consent/config | first-party identity events deleted; vendor deletion required by runbook |
| Session/rate-limit keys | security and continuity | Redis/browser cookie | application | TTL expiry; active session cleared on deletion/logout |
| Waitlist email | requested communication | user DB/SMTP | email owner | delete on request or campaign-policy expiry |
| Security/operational logs | incident detection | hosting/Sentry | application | redact and expire under approved logging policy |
| Public market analyses | public research, cache reuse | market DB/caches | public/provider source | not user-owned; retained under data license |

Retention durations, backup expiry, vendor deletion SLAs, and legal basis require privacy/legal approval before certification.
