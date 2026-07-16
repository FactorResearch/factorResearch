"""Typed schema and asynchronous-state contracts for repeatable UI sections."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class UIState(StrEnum):
    IDLE = "idle"
    LOADING = "loading"
    REFRESHING = "refreshing"
    PARTIAL = "partial"
    SUCCESS = "success"
    EMPTY = "empty"
    STALE = "stale"
    WARNING = "warning"
    ERROR = "error"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class InteractionState(StrEnum):
    """Documented visual/semantic states shared by interactive primitives."""

    DEFAULT = "default"
    HOVER = "hover"
    FOCUS_VISIBLE = "focus-visible"
    ACTIVE = "active"
    SELECTED = "selected"
    DISABLED = "disabled"
    LOADING = "loading"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    READ_ONLY = "read-only"


@dataclass(frozen=True)
class SectionState:
    state: UIState
    message: str = ""
    progress: int | None = None
    retry_id: str | dict | None = None
    stale_content: object | None = None

    def __post_init__(self) -> None:
        if self.progress is not None and not 0 <= self.progress <= 100:
            raise ValueError("progress must be between 0 and 100")


@dataclass(frozen=True)
class SectionDefinition:
    id: str
    component: str
    priority: int
    data_dependency: str
    loading_treatment: str = "skeleton"
    error_policy: str = "retry"
    entitlement: str | None = None
    responsive_span: int = 12
    deferred: bool = False
    allow_stale: bool = True
    analytics_id: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.id.replace("-", "").isalnum():
            raise ValueError("section id must be a stable kebab-case identifier")
        if not 1 <= self.responsive_span <= 12:
            raise ValueError("responsive_span must be from 1 to 12")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")


class SectionRegistry:
    """Small renderer registry; business calculations remain outside the UI."""

    def __init__(self, renderers: Mapping[str, Callable[[object], object]]) -> None:
        self._renderers = dict(renderers)

    def render(
        self, definitions: Sequence[SectionDefinition], data: Mapping[str, object]
    ) -> list[object]:
        rendered: list[object] = []
        seen: set[str] = set()
        for definition in sorted(definitions, key=lambda item: (item.priority, item.id)):
            if definition.id in seen:
                raise ValueError(f"duplicate section id: {definition.id}")
            seen.add(definition.id)
            try:
                renderer = self._renderers[definition.component]
            except KeyError as exc:
                raise ValueError(f"unknown section component: {definition.component}") from exc
            rendered.append(renderer(data.get(definition.data_dependency)))
        return rendered
