from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


class BudgetExceeded(RuntimeError):
    pass


@dataclass(slots=True)
class AtomicBudgetLimits:
    max_total_actions: int = 100
    per_tool: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class TaskBudgetLimits:
    max_actions: int = 100
    max_entities: int = 32
    max_material_cost: int = 1000
    max_duration_sec: float = 300.0
    max_failures: int = 5
    max_replans: int = 2


@dataclass(slots=True)
class BudgetSnapshot:
    actions: int
    entities: int
    material_cost: int
    failures: int
    replans: int
    started_at_epoch: float
    elapsed_sec: float
    per_tool: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BudgetContext:
    """Shared two-level budget for every atomic tool and the whole task.

    Batch executors do not bypass this object: every internal atomic call must
    still consume an atomic action. The stricter of atomic and task limits wins.
    Counters can be persisted and restored across Controller restarts.
    """

    def __init__(self, atomic: AtomicBudgetLimits | None = None, task: TaskBudgetLimits | None = None, *, restored: Mapping[str, Any] | None = None) -> None:
        self.atomic = atomic or AtomicBudgetLimits()
        self.task = task or TaskBudgetLimits()
        restored = restored or {}
        self.started_at_epoch = float(restored.get("started_at_epoch", time.time()))
        self.actions = int(restored.get("actions", 0))
        self.entities = int(restored.get("entities", 0))
        self.material_cost = int(restored.get("material_cost", 0))
        self.failures = int(restored.get("failures", 0))
        self.replans = int(restored.get("replans", 0))
        self.per_tool = {str(k): int(v) for k, v in dict(restored.get("per_tool", {})).items()}

    def _elapsed(self) -> float:
        return max(0.0, time.time() - self.started_at_epoch)

    def _check_duration(self) -> None:
        if self._elapsed() > self.task.max_duration_sec:
            raise BudgetExceeded("task duration budget exceeded")

    def consume_atomic(self, tool: str, *, entities: int = 0, material_cost: int = 0) -> None:
        self._check_duration()
        next_actions = self.actions + 1
        if next_actions > min(self.atomic.max_total_actions, self.task.max_actions):
            raise BudgetExceeded("action budget exceeded")
        next_tool_count = self.per_tool.get(tool, 0) + 1
        tool_limit = self.atomic.per_tool.get(tool)
        if tool_limit is not None and next_tool_count > tool_limit:
            raise BudgetExceeded(f"atomic tool budget exceeded for {tool}")
        if self.entities + entities > self.task.max_entities:
            raise BudgetExceeded("entity budget exceeded")
        if self.material_cost + material_cost > self.task.max_material_cost:
            raise BudgetExceeded("material budget exceeded")
        self.actions = next_actions
        self.per_tool[tool] = next_tool_count
        self.entities += entities
        self.material_cost += material_cost

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures > self.task.max_failures:
            raise BudgetExceeded("failure budget exceeded")

    def record_replan(self) -> None:
        self.replans += 1
        if self.replans > self.task.max_replans:
            raise BudgetExceeded("replan budget exceeded")

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(actions=self.actions, entities=self.entities, material_cost=self.material_cost, failures=self.failures, replans=self.replans, started_at_epoch=self.started_at_epoch, elapsed_sec=self._elapsed(), per_tool=dict(self.per_tool))
