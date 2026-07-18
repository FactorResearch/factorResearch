# Feature management service

ISSUE_044 provides the single runtime decision point for product feature
availability. Callers use `codes.services.feature_management.evaluate()` and
must not inspect subscription plan names or feature-flag files directly.

## Definition format

Definitions are stored in `feature_management.json` for local operation and
can be mirrored through Redis for multi-process deployments. A missing or
malformed definition is disabled. Each definition records an owner, purpose,
default state, rollout controls, dependencies, and expiry/removal metadata.

Supported gates are:

- global enablement;
- deterministic percentage rollout by stable user identifier;
- subscription tiers;
- region/country code;
- internal users and beta users;
- dependency features;
- emergency kill switch.

All gates are conjunctive. A kill switch or disabled dependency wins over every
other gate. Rollout bucketing is deterministic, so a user does not move between
buckets during a process restart.

## Runtime and operations

The service checks the backing definition's file modification time and uses a
short in-process cache. Redis, when configured, is the shared source for
multi-worker deployments. `set_definition()` and `set_kill_switch()` publish
the new state, invalidate the local cache, and append a redacted audit record;
therefore safe feature changes do not require an application deployment.

The mutation methods are administrative infrastructure boundaries. They must be
called only by an authenticated, authorized operations surface. The evaluator
never trusts client-provided plan names for authorization and returns a denied
decision for unknown features, invalid definitions, failed dependencies, or
backing-store errors.

## Observability and rollback

Every mutation records actor, feature, action, outcome, and timestamp without
recording secrets or full user context. Evaluation is intentionally side-effect
free; callers may add product telemetry for exposure and conversion. To roll
back, restore the prior definition or set its kill switch to `true`, then verify
the audit record and affected decision path.
