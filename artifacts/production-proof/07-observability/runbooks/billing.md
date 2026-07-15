# Billing Webhook Failure

1. Confirm Stripe status, webhook age, signature failures, and endpoint response codes.
2. Never grant entitlement from client-provided state. Preserve signature verification and event idempotency.
3. Pause subscription reconciliation changes if event ordering or authenticity is uncertain.
4. Repair the endpoint, then replay events from Stripe in timestamp order; duplicates must remain no-ops.
5. Reconcile affected subscriptions against Stripe and record mismatches without storing payment details.
6. Escalate charge, entitlement, or customer-notification discrepancies to payments and incident command.
