"""Deterministic operational health evaluation and bounded remediation.

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

    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    CONSTRAINED = "CONSTRAINED"
    RECOVERING = "RECOVERING"
    UNAVAILABLE = "UNAVAILABLE"


class WorkloadPriority(StrEnum):
    """Priority classes used to protect essential workflows."""

    ESSENTIAL = "essential"
    OPTIONAL = "optional"


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
        return {
            "state": aggregate.value,
            "components": {name: report.as_dict() for name, report in current.items()},
            "observation_only": self.observation_only,
        }

    @staticmethod
    def allow_work(priority: WorkloadPriority, state: OperationalState) -> bool:
        """Keep essential workflows available while shedding optional work."""
        if priority == WorkloadPriority.ESSENTIAL:
            return state != OperationalState.UNAVAILABLE
        return state in {OperationalState.WATCH, OperationalState.DEGRADED}


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
