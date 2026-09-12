from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


class BudgetExceeded(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


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
    task_id: str | None
    atomic_actions: int
    task_actions: int
    entities: int
    material_cost: int
    failures: int
    replans: int
    started_at_epoch: float
    elapsed_sec: float
    per_tool: dict[str, int]

    @property
    def actions(self) -> int:
        return self.task_actions

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["actions"] = self.task_actions
        return data


class BudgetContext:
    def __init__(self, atomic: AtomicBudgetLimits | None = None, task: TaskBudgetLimits | None = None, *, task_id: str | None = None, restored: Mapping[str, Any] | None = None, initial_replans: int = 0) -> None:
        self.atomic = atomic or AtomicBudgetLimits()
        self.task = task or TaskBudgetLimits()
        restored = dict(restored or {})
        if restored and restored.get("task_id") != task_id:
            restored = {}
        self.task_id = task_id
        self.started_at_epoch = float(restored.get("started_at_epoch", time.time()))
        legacy_actions = int(restored.get("actions", 0) or 0)
        self.atomic_actions = int(restored.get("atomic_actions", legacy_actions) or 0)
        self.task_actions = int(restored.get("task_actions", legacy_actions) or 0)
        self.entities = int(restored.get("entities", 0) or 0)
        self.material_cost = int(restored.get("material_cost", 0) or 0)
        self.failures = int(restored.get("failures", 0) or 0)
        self.replans = int(restored.get("replans", initial_replans) or 0)
        self.per_tool = {str(k): int(v) for k, v in dict(restored.get("per_tool", {})).items()}

    @property
    def actions(self) -> int:
        return self.task_actions

    def _elapsed(self) -> float:
        return max(0.0, time.time() - self.started_at_epoch)

    def _check_duration(self) -> None:
        if self._elapsed() > self.task.max_duration_sec:
            raise BudgetExceeded("TASK_BUDGET_EXCEEDED", "task duration budget exceeded")

    def consume_atomic(self, tool: str, *, entities: int = 0, material_cost: int = 0) -> None:
        self._check_duration()
        if self.atomic_actions + 1 > self.atomic.max_total_actions:
            raise BudgetExceeded("ATOMIC_BUDGET_EXCEEDED", "atomic action budget exceeded")
        if self.task_actions + 1 > self.task.max_actions:
            raise BudgetExceeded("TASK_BUDGET_EXCEEDED", "task action budget exceeded")
        next_tool_count = self.per_tool.get(tool, 0) + 1
        tool_limit = self.atomic.per_tool.get(tool)
        if tool_limit is not None and next_tool_count > tool_limit:
            raise BudgetExceeded("ATOMIC_BUDGET_EXCEEDED", f"atomic tool budget exceeded for {tool}")
        if self.entities + entities > self.task.max_entities:
            raise BudgetExceeded("TASK_BUDGET_EXCEEDED", "entity budget exceeded")
        if self.material_cost + material_cost > self.task.max_material_cost:
            raise BudgetExceeded("TASK_BUDGET_EXCEEDED", "material budget exceeded")
        self.atomic_actions += 1
        self.task_actions += 1
        self.per_tool[tool] = next_tool_count
        self.entities += entities
        self.material_cost += material_cost

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures > self.task.max_failures:
            raise BudgetExceeded("TASK_BUDGET_EXCEEDED", "failure budget exceeded")

    def record_replan(self) -> None:
        self.replans += 1
        if self.replans > self.task.max_replans:
            raise BudgetExceeded("REPLAN_BUDGET_EXCEEDED", "replan budget exceeded")

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(task_id=self.task_id, atomic_actions=self.atomic_actions, task_actions=self.task_actions, entities=self.entities, material_cost=self.material_cost, failures=self.failures, replans=self.replans, started_at_epoch=self.started_at_epoch, elapsed_sec=self._elapsed(), per_tool=dict(self.per_tool))
