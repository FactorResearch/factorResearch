"""Acceptance tests for weighted and priority-aware traffic control."""

import codes.app_modules.rate_limit as rate_limit


def setup_function() -> None:
    rate_limit._RATE_LIMIT_STORE.clear()


def test_expensive_operations_consume_multiple_budget_units() -> None:
    rate_limit.check_rate_limit("analysis", calls=10, period_seconds=60, key="user-1", cost=7)
    try:
        rate_limit.check_rate_limit("analysis", calls=10, period_seconds=60, key="user-1", cost=4)
    except rate_limit.RateLimited as error:
        assert error.retry_after >= 0
    else:
        raise AssertionError("weighted cost must consume more than one unit")


def test_optional_traffic_preserves_capacity_for_essential_work() -> None:
    rate_limit.check_rate_limit(
        "shared", calls=10, period_seconds=60, key="user-1", cost=8, priority="optional"
    )
    try:
        rate_limit.check_rate_limit(
            "shared", calls=10, period_seconds=60, key="user-1", cost=2, priority="essential"
        )
    except rate_limit.RateLimited as error:
        raise AssertionError("essential traffic should use the reserved capacity") from error


def test_invalid_priority_and_cost_fail_closed() -> None:
    for kwargs in ({"cost": 0}, {"priority": "unknown"}):
        try:
            rate_limit.check_rate_limit("invalid", calls=10, period_seconds=60, key="user-1", **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid traffic policy input must fail closed")
