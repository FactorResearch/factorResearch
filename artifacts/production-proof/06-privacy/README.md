# Phase 6 Privacy Evidence

**Status:** Data inventory and first-party deletion controls implemented; legal/vendor certification remains open.  
**Evidence date:** 2026-07-14

Account deletion now removes portfolio data, user weights, usage, local subscription metadata, first-party analytics events, and private custom snapshots, then clears session/cache/rate-limit state. Public ticker-level market records are not user-owned and remain.

## Open Release Blockers

- [ ] Approve legal basis, exact retention periods, backup expiry, and jurisdiction obligations.
- [ ] Implement/export a user-readable data export.
- [ ] Automate Auth0, Stripe, analytics-vendor, email, and error-monitor deletion requests where contractually supported.
- [ ] Run deletion through active stores, caches, vendors, logs, and backup-expiry verification.
- [ ] Record terms/privacy policy versions and consent where legally required.
- [ ] Complete vendor DPAs, license review, and legal signoff.
