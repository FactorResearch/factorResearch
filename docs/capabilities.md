# Capability authorization (ISSUE_046)

`codes.services.capabilities.CapabilityService` is the server-side policy
boundary for feature access. Endpoint and UI code asks for a capability (for
example, `backtest`) through `permissions.can_access_feature`; it does not
inspect subscription tier names.

## Policy configuration

The checked-in [`capabilities.json`](../capabilities.json) maps subscription
records to capabilities and declares capability dependencies. Policy changes,
including future pricing entitlement changes, are made in this configuration
and take effect after the policy file is reloaded. The service validates all
capability and plan references before activating a new policy. Missing,
malformed, cyclic, or unknown policy data denies access.

## Overrides and caching

Overrides are keyed by authenticated user ID and capability, require an actor,
and always have a timezone-aware future expiry. They are held behind the
service boundary and invalidate cached decisions when changed. Decisions have
a one-second in-process TTL and include the policy generation in their cache
key; policy file changes invalidate the cache.

An enabled override cannot bypass a capability dependency. A disabled override
denies the capability even when the subscription policy grants it. Expired
overrides are removed on evaluation.

## Security boundary

The authenticated user ID is supplied by the existing server authentication
boundary. Administrative code must authorize who may create or clear an
override before calling the service and should retain an audit record for the
actor and reason. The service does not log user content or subscription data.
All failure paths are fail-closed.
