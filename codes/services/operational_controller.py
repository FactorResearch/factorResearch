"""Deterministic operational modes, health evaluation, and bounded remediation.

The controller is an application-layer coordinator. It evaluates registered
health probes and may run only explicitly registered recovery actions; it does
not infer fixes, restart processes, mutate financial data, or call an AI model.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from codes.services.audit_journal import audit_journal


class OperationalState(StrEnum):
    """Stable states exposed to dashboards and release checks."""

    NORMAL = "NORMAL"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    CONSTRAINED = "CONSTRAINED"
    RECOVERING = "RECOVERING"
    UNAVAILABLE = "UNAVAILABLE"
    READ_ONLY = "READ_ONLY"
    MAINTENANCE = "MAINTENANCE"
    EMERGENCY = "EMERGENCY"


# ``OperationalMode`` is the platform vocabulary used by ISSUE_056. Keeping
# the health-state name above preserves the ISSUE_043 probe contract while
# making the one-active-mode invariant explicit to callers.
OperationalMode = OperationalState


class WorkloadPriority(StrEnum):
    """Priority classes used to protect essential workflows."""

    ESSENTIAL = "essential"
    OPTIONAL = "optional"


@dataclass(frozen=True)
class ModeTransition:
    """Auditable change from one platform mode to another."""

    previous: OperationalMode
    current: OperationalMode
    reason: str
    changed_at: float

    def as_dict(self) -> dict[str, Any]:
        """Return the transition in the operational telemetry format."""
        return {
            "previous": self.previous.value,
            "current": self.current.value,
            "reason": self.reason,
            "changed_at": self.changed_at,
        }


@dataclass(frozen=True)
class HealthReport:
    """Normalized result of one deterministic health probe."""

    component: str
    state: OperationalState
    reason: str
    metrics: dict[str, Any]
    checked_at: float

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe report for telemetry and dashboards."""
        return {
            "component": self.component,
            "state": self.state.value,
            "reason": self.reason,
            "metrics": dict(self.metrics),
            "checked_at": self.checked_at,
        }


@dataclass(frozen=True)
class RecoveryAction:
    """Allowlisted, bounded remediation with a mandatory verification probe."""

    name: str
    component: str
    action: Callable[[], bool]
    verify: Callable[[], bool]
    max_attempts: int = 1
    cooldown_seconds: float = 60.0


class OperationalController:
    """Evaluate platform health and execute safe recovery actions.

    Probes return either a mapping containing ``state`` and ``reason`` or a
    fully formed ``HealthReport``. The controller is observation-only unless
    ``observation_only`` is explicitly disabled. Recovery is bounded by each
    action's attempt and cooldown limits, and a failed verification leaves the
    component degraded rather than claiming success.
    """

    def __init__(self, *, observation_only: bool = True, clock: Callable[[], float] | None = None) -> None:
        self.observation_only = observation_only
        self._clock = clock or time.time
        self._probes: dict[str, Callable[[], Mapping[str, Any] | HealthReport]] = {}
        self._actions: dict[str, RecoveryAction] = {}
        self._attempts: dict[str, int] = {}
        self._last_action: dict[str, float] = {}
        self._lock = threading.RLock()
        self._mode = OperationalMode.NORMAL
        self._mode_changed_at = self._clock()
        self._last_transition: ModeTransition | None = None
        self._recovery_confirmations = 0

    def register_probe(
        self,
        component: str,
        probe: Callable[[], Mapping[str, Any] | HealthReport],
    ) -> None:
        """Register or replace a deterministic component health probe."""
        if not component.strip():
            raise ValueError("component is required")
        with self._lock:
            self._probes[component] = probe

    def register_recovery(self, action: RecoveryAction) -> None:
        """Register one explicit recovery action and reject unsafe bounds."""
        if action.max_attempts < 1 or action.cooldown_seconds < 0:
            raise ValueError("recovery bounds must be positive")
        with self._lock:
            self._actions[action.name] = action

    def evaluate(self) -> dict[str, HealthReport]:
        """Run all probes and convert probe failures to UNAVAILABLE reports."""
        with self._lock:
            probes = dict(self._probes)
        reports: dict[str, HealthReport] = {}
        for component, probe in probes.items():
            checked_at = self._clock()
            try:
                result = probe()
                if isinstance(result, HealthReport):
                    reports[component] = result
                    continue
                state = OperationalState(str(result.get("state", OperationalState.WATCH)))
                reports[component] = HealthReport(
                    component=component,
                    state=state,
                    reason=str(result.get("reason", "health check completed")),
                    metrics=dict(result.get("metrics") or {}),
                    checked_at=checked_at,
                )
            except Exception as exc:
                reports[component] = HealthReport(
                    component=component,
                    state=OperationalState.UNAVAILABLE,
                    reason=f"health probe failed: {type(exc).__name__}",
                    metrics={},
                    checked_at=checked_at,
                )
        return reports

    def recover(self, *, reports: Mapping[str, HealthReport] | None = None) -> list[dict[str, Any]]:
        """Attempt allowlisted remediations and verify each result.

        No action runs in observation-only mode. Actions with exhausted attempt
        budgets or active cooldowns are skipped and reported, making the
        controller safe to call repeatedly from a scheduler.
        """
        current = reports or self.evaluate()
        with self._lock:
            actions = list(self._actions.values())
        outcomes = []
        for action in actions:
            report = current.get(action.component)
            if report is None or report.state in {OperationalState.WATCH}:
                continue
            now = self._clock()
            attempts = self._attempts.get(action.name, 0)
            if self.observation_only:
                outcomes.append({"action": action.name, "status": "observed"})
                continue
            if attempts >= action.max_attempts:
                outcomes.append({"action": action.name, "status": "attempt_limit"})
                continue
            if now - self._last_action.get(action.name, 0.0) < action.cooldown_seconds:
                outcomes.append({"action": action.name, "status": "cooldown"})
                continue
            self._attempts[action.name] = attempts + 1
            self._last_action[action.name] = now
            verified = False
            try:
                action.action()
                verified = bool(action.verify())
            except Exception:
                verified = False
            status = "verified" if verified else "verification_failed"
            outcomes.append({"action": action.name, "status": status})
            audit_journal.record(
                "operational_recovery",
                action=action.name,
                component=action.component,
                outcome=status,
                severity="INFO" if verified else "ERROR",
            )
        return outcomes

    def summary(self, reports: Mapping[str, HealthReport] | None = None) -> dict[str, Any]:
        """Return aggregate state and component reports for operational telemetry."""
        current = reports or self.evaluate()
        states = [report.state for report in current.values()]
        aggregate = OperationalState.WATCH
        for candidate in (
            OperationalState.UNAVAILABLE,
            OperationalState.RECOVERING,
            OperationalState.CONSTRAINED,
            OperationalState.DEGRADED,
        ):
            if candidate in states:
                aggregate = candidate
                break
        self.reconcile(current)
        return {
            "state": aggregate.value,
            "mode": self.active_mode.value,
            "message": self.mode_message,
            "components": {name: report.as_dict() for name, report in current.items()},
            "observation_only": self.observation_only,
            "last_transition": (
                self._last_transition.as_dict() if self._last_transition else None
            ),
        }

    def reconcile(self, reports: Mapping[str, HealthReport]) -> bool:
        """Derive a platform mode from component health without oscillation."""
        states = [report.state for report in reports.values()]
        desired = OperationalMode.NORMAL
        for candidate in (
            OperationalMode.EMERGENCY,
            OperationalMode.UNAVAILABLE,
            OperationalMode.RECOVERING,
            OperationalMode.CONSTRAINED,
            OperationalMode.DEGRADED,
            OperationalMode.WATCH,
        ):
            if candidate in states:
                desired = candidate
                break
        current = self.active_mode
        # Explicit operator modes remain authoritative until explicitly changed.
        if current in {
            OperationalMode.READ_ONLY,
            OperationalMode.MAINTENANCE,
            OperationalMode.EMERGENCY,
        }:
            return False
        current_rank = MODE_SEVERITY[current]
        desired_rank = MODE_SEVERITY[desired]
        return self.transition(
            desired,
            reason=f"health reconciliation: {desired.value.lower()}",
            minimum_dwell_seconds=30.0 if desired_rank <= current_rank else 0.0,
            recovery_confirmations=2,
        )

    @property
    def active_mode(self) -> OperationalMode:
        """Return the single current platform mode."""
        with self._lock:
            return self._mode

    @property
    def mode_message(self) -> str:
        """Return concise copy suitable for a banner or operational response."""
        return MODE_MESSAGES[self.active_mode]

    def transition(
        self,
        mode: OperationalMode,
        *,
        reason: str,
        minimum_dwell_seconds: float = 30.0,
        recovery_confirmations: int = 2,
        actor: str = "system",
    ) -> bool:
        """Move to a requested mode when anti-oscillation rules permit it.

        Manual safety modes (READ_ONLY, MAINTENANCE, and EMERGENCY) take
        effect immediately. Automatic transitions out of a safety mode require
        the configured number of consecutive recovery confirmations, while
        ordinary automatic transitions respect a minimum dwell time. Every
        accepted transition is written to the redacted operational journal.
        """
        if minimum_dwell_seconds < 0 or recovery_confirmations < 1:
            raise ValueError("transition bounds must be non-negative and confirmations positive")
        target = OperationalMode(mode)
        now = self._clock()
        with self._lock:
            current = self._mode
            if target == current:
                self._recovery_confirmations = 0
                return False
            safety_mode = current in {
                OperationalMode.READ_ONLY,
                OperationalMode.MAINTENANCE,
                OperationalMode.EMERGENCY,
            }
            if safety_mode and target not in {
                OperationalMode.READ_ONLY,
                OperationalMode.MAINTENANCE,
                OperationalMode.EMERGENCY,
            }:
                self._recovery_confirmations += 1
                if self._recovery_confirmations < recovery_confirmations:
                    return False
            elif now - self._mode_changed_at < minimum_dwell_seconds:
                return False
            previous = current
            self._mode = target
            self._mode_changed_at = now
            self._recovery_confirmations = 0
            self._last_transition = ModeTransition(previous, target, str(reason)[:256], now)
        audit_journal.record(
            "operational_mode_transition",
            action="transition",
            actor_id=actor,
            component="operational_controller",
            details=self._last_transition.as_dict(),
        )
        return True

    def set_mode(self, mode: OperationalMode, *, reason: str, actor: str) -> bool:
        """Apply an operator-requested mode without bypassing audit logging."""
        return self.transition(
            mode,
            reason=reason,
            minimum_dwell_seconds=0.0,
            recovery_confirmations=1,
            actor=actor,
        )

    @staticmethod
    def allow_work(priority: WorkloadPriority, state: OperationalState) -> bool:
        """Keep essential workflows available while shedding optional work."""
        if priority == WorkloadPriority.ESSENTIAL:
            return state not in {
                OperationalState.UNAVAILABLE,
                OperationalState.EMERGENCY,
            }
        return state in {OperationalState.NORMAL, OperationalState.WATCH}

    @staticmethod
    def allow_mode_work(priority: WorkloadPriority, mode: OperationalMode) -> bool:
        """Apply mode policy before dispatching an essential or optional task."""
        if mode in {OperationalMode.EMERGENCY, OperationalMode.MAINTENANCE}:
            return False
        if mode == OperationalMode.READ_ONLY:
            return priority == WorkloadPriority.ESSENTIAL
        if priority == WorkloadPriority.ESSENTIAL:
            return True
        return mode in {OperationalMode.NORMAL, OperationalMode.WATCH}


MODE_MESSAGES: dict[OperationalMode, str] = {
    OperationalMode.NORMAL: "All platform functions are operating normally.",
    OperationalMode.WATCH: "The platform is being closely monitored; some responses may be slower.",
    OperationalMode.DEGRADED: "Some optional functions are temporarily limited while core workflows remain available.",
    OperationalMode.CONSTRAINED: "Optional processing is paused to protect essential workflows.",
    OperationalMode.READ_ONLY: "The platform is read-only while changes are temporarily paused.",
    OperationalMode.MAINTENANCE: "Scheduled maintenance is in progress; changes are temporarily unavailable.",
    OperationalMode.RECOVERING: "The platform is recovering; availability may change while checks complete.",
    OperationalMode.EMERGENCY: "Emergency protection is active; platform operations are temporarily paused.",
    OperationalMode.UNAVAILABLE: "The platform is temporarily unavailable; please try again later.",
}

# Higher values represent greater customer impact. A worsening report may
# change mode immediately; recovery is deliberately slower and confirmed.
MODE_SEVERITY: dict[OperationalMode, int] = {
    OperationalMode.NORMAL: 0,
    OperationalMode.WATCH: 1,
    OperationalMode.DEGRADED: 2,
    OperationalMode.CONSTRAINED: 3,
    OperationalMode.RECOVERING: 4,
    OperationalMode.READ_ONLY: 5,
    OperationalMode.MAINTENANCE: 6,
    OperationalMode.UNAVAILABLE: 7,
    OperationalMode.EMERGENCY: 8,
}


def classify_runtime_health(component: str, payload: Mapping[str, Any]) -> HealthReport:
    """Normalize provider and queue health payloads into controller states."""
    now = time.time()
    if payload.get("backend") == "unavailable" or payload.get("status") == "unavailable":
        return HealthReport(component, OperationalState.UNAVAILABLE, "runtime backend unavailable", dict(payload), now)
    if int(payload.get("dead_letter", 0) or 0) > 0:
        return HealthReport(component, OperationalState.DEGRADED, "dead-letter work present", dict(payload), now)
    if any(float(value.get("opened_at", 0) or 0) > 0 for value in payload.values() if isinstance(value, Mapping)):
        return HealthReport(component, OperationalState.UNAVAILABLE, "provider circuit open", dict(payload), now)
    if any(int(value.get("failures", 0) or 0) > 0 for value in payload.values() if isinstance(value, Mapping)):
        return HealthReport(component, OperationalState.CONSTRAINED, "provider failures observed", dict(payload), now)
    return HealthReport(component, OperationalState.WATCH, "runtime checks are healthy", dict(payload), now)


controller = OperationalController()
