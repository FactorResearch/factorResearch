# Secret Compromise

1. Declare a security incident, preserve access evidence, and identify secret scope without copying its value.
2. Revoke or rotate the secret at its authority first; then update the secrets manager and deployments.
3. Invalidate sessions, tokens, webhooks, or provider credentials according to the exposed capability.
4. Search audit logs for use from issuance through revocation and isolate suspicious actors.
5. Verify old credentials fail and new credentials work from each service role.
6. Notify vendors, privacy/legal, and affected users according to the incident plan.
