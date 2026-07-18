from codes.services.operational_controller import (
    HealthReport,
    OperationalController,
    OperationalState,
    RecoveryAction,
    WorkloadPriority,
)


def test_probe_failure_is_unavailable_and_summary_is_deterministic() -> None:
    controller = OperationalController(clock=lambda: 10.0)
    controller.register_probe("queue", lambda: {"state": "DEGRADED", "reason": "heartbeat old"})
    controller.register_probe("database", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    reports = controller.evaluate()
    assert reports["queue"].state == OperationalState.DEGRADED
    assert reports["database"].state == OperationalState.UNAVAILABLE
    assert controller.summary(reports)["state"] == "UNAVAILABLE"


def test_observation_only_never_executes_recovery() -> None:
    calls = []
    controller = OperationalController(observation_only=True, clock=lambda: 10.0)
    controller.register_probe("provider", lambda: HealthReport("provider", OperationalState.CONSTRAINED, "quota", {}, 10.0))
    controller.register_recovery(RecoveryAction("fallback", "provider", lambda: calls.append("action") or True, lambda: True))
    assert controller.recover()[0]["status"] == "observed"
    assert calls == []


def test_recovery_is_bounded_and_requires_verification() -> None:
    calls = []
    controller = OperationalController(observation_only=False, clock=lambda: 10.0)
    report = HealthReport("cache", OperationalState.DEGRADED, "stale", {}, 10.0)
    controller.register_recovery(RecoveryAction("cache-fallback", "cache", lambda: calls.append(1) or True, lambda: False, max_attempts=1, cooldown_seconds=0))
    assert controller.recover(reports={"cache": report})[0]["status"] == "verification_failed"
    assert controller.recover(reports={"cache": report})[0]["status"] == "attempt_limit"
    assert calls == [1]


def test_essential_work_is_protected_before_optional_work() -> None:
    assert OperationalController.allow_work(WorkloadPriority.ESSENTIAL, OperationalState.CONSTRAINED)
    assert not OperationalController.allow_work(WorkloadPriority.OPTIONAL, OperationalState.CONSTRAINED)
    assert not OperationalController.allow_work(WorkloadPriority.OPTIONAL, OperationalState.RECOVERING)
    assert not OperationalController.allow_work(WorkloadPriority.ESSENTIAL, OperationalState.UNAVAILABLE)
