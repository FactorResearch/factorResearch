"""Behavioral tests for ISSUE_046 capability authorization."""

from datetime import datetime, timedelta, timezone
import json

from codes.services.capabilities import CapabilityService


def _policy(**overrides):
    policy = {
        "version": "test-1",
        "plans": {"free": {"capabilities": ["analysis"]}},
        "capabilities": {
            "analysis": {"dependencies": []},
            "backtest": {"dependencies": ["analysis"]},
        },
    }
    policy.update(overrides)
    return policy


def _service(tmp_path, policy):
    path = tmp_path / "capabilities.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    return CapabilityService(path)


def test_capability_policy_grants_configured_access_and_denies_missing(tmp_path):
    service = _service(tmp_path, _policy())

    assert service.evaluate("u1", "analysis", plan="free", status="trialing").allowed
    denied = service.evaluate("u1", "backtest", plan="free", status="trialing")
    assert denied.allowed is False
    assert service.evaluate("u1", "unknown", plan="free", status="trialing").allowed is False


def test_temporary_override_is_user_scoped_and_expires(tmp_path):
    service = _service(tmp_path, _policy())
    now = datetime.now(timezone.utc)
    service.set_override("u1", "backtest", enabled=True, expires_at=now + timedelta(minutes=5), actor="admin")

    assert service.evaluate("u1", "backtest", plan="free", status="trialing", now=now).allowed
    assert not service.evaluate("u2", "backtest", plan="free", status="trialing", now=now).allowed
    assert not service.evaluate("u1", "backtest", plan="free", status="trialing", now=now + timedelta(minutes=6)).allowed


def test_policy_changes_are_configuration_only_and_invalidate_decisions(tmp_path):
    policy = _policy()
    service = _service(tmp_path, policy)
    path = tmp_path / "capabilities.json"
    assert not service.evaluate("u1", "backtest", plan="free", status="trialing").allowed

    policy["plans"]["free"]["capabilities"].append("backtest")
    path.write_text(json.dumps(policy), encoding="utf-8")
    assert service.evaluate("u1", "backtest", plan="free", status="trialing").allowed


def test_invalid_policy_fails_closed(tmp_path):
    service = _service(tmp_path, {"version": "broken", "plans": {}, "capabilities": {}})
    assert not service.evaluate("u1", "analysis", plan="free", status="trialing").allowed
