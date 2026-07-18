"""Acceptance tests for ISSUE_056 platform modes and graceful degradation."""

from codes.services.operational_controller import (
    HealthReport,
    OperationalController,
    OperationalMode,
    OperationalState,
    WorkloadPriority,
)


def test_controller_has_one_normal_mode_and_clear_message() -> None:
    controller = OperationalController(clock=lambda: 100.0)

    assert controller.active_mode == OperationalMode.NORMAL
    assert controller.mode_message.startswith("All platform")
    assert controller.summary({})["mode"] == "NORMAL"


def test_safety_mode_is_audited_and_recovers_without_oscillation() -> None:
    now = [100.0]
    controller = OperationalController(clock=lambda: now[0])

    assert controller.set_mode(OperationalMode.READ_ONLY, reason="database maintenance", actor="ops")
    assert not controller.transition(
        OperationalMode.NORMAL,
        reason="first healthy check",
        recovery_confirmations=2,
    )
    assert controller.active_mode == OperationalMode.READ_ONLY
    assert controller.transition(
        OperationalMode.NORMAL,
        reason="second healthy check",
        recovery_confirmations=2,
    )
    assert controller.active_mode == OperationalMode.NORMAL


def test_mode_policy_sheds_optional_work_first() -> None:
    assert OperationalController.allow_mode_work(WorkloadPriority.ESSENTIAL, OperationalMode.DEGRADED)
    assert not OperationalController.allow_mode_work(WorkloadPriority.OPTIONAL, OperationalMode.DEGRADED)
    assert OperationalController.allow_mode_work(WorkloadPriority.ESSENTIAL, OperationalMode.READ_ONLY)
    assert not OperationalController.allow_mode_work(WorkloadPriority.OPTIONAL, OperationalMode.READ_ONLY)
    assert not OperationalController.allow_mode_work(WorkloadPriority.ESSENTIAL, OperationalMode.EMERGENCY)


def test_health_reconciliation_enters_degraded_mode_immediately() -> None:
    controller = OperationalController(clock=lambda: 100.0)
    reports = {
        "provider": HealthReport(
            "provider", OperationalState.DEGRADED, "quota", {}, 100.0
        )
    }

    assert controller.reconcile(reports)
    assert controller.active_mode == OperationalMode.DEGRADED
