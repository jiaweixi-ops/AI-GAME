from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from .budget import AtomicBudgetLimits, BudgetContext, TaskBudgetLimits
from .storage import JsonStateStore
from .types import Condition, TaskSpec, ToolResult
from .verified_tools import VerifiedToolSurface
from .watchdog import Watchdog, WatchdogEvent


def _resolve_path(root: Mapping[str, Any], path: str) -> Any:
    cur: Any = root
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def evaluate_condition(root: Mapping[str, Any], condition: Condition) -> bool:
    actual = _resolve_path(root, condition.path)
    expected = condition.value
    op = condition.op
    if op == "eq": return actual == expected
    if op == "ne": return actual != expected
    if op == "truthy": return bool(actual)
    if op == "falsy": return not bool(actual)
    if op == "contains":
        try: return expected in actual
        except TypeError: return False
    try:
        if op == "gt": return actual > expected
        if op == "gte": return actual >= expected
        if op == "lt": return actual < expected
        if op == "lte": return actual <= expected
    except TypeError:
        return False
    return False


@dataclass(slots=True)
class KeeperPolicy:
    atomic: AtomicBudgetLimits = field(default_factory=lambda: AtomicBudgetLimits(max_total_actions=100))
    task: TaskBudgetLimits = field(default_factory=lambda: TaskBudgetLimits(max_actions=100, max_entities=32, max_material_cost=1000, max_duration_sec=300, max_failures=5, max_replans=2))


@dataclass(slots=True)
class KeeperResult:
    status: str
    reason: str | None
    task: TaskSpec
    watchdog_events: list[WatchdogEvent] = field(default_factory=list)
    last_tool_result: ToolResult | None = None


class Keeper:
    """Deterministic V0 task executor with persisted cursor and budget state."""

    def __init__(self, bridge, store: JsonStateStore, watchdog: Watchdog, policy: KeeperPolicy | None = None) -> None:
        self.bridge = bridge
        self.store = store
        self.watchdog = watchdog
        self.policy = policy or KeeperPolicy()
        self.action_log: list[dict[str, Any]] = []

    def _budget(self) -> BudgetContext:
        return BudgetContext(self.policy.atomic, self.policy.task, restored=self.store.load_runtime())

    def _persist_budget(self, budget: BudgetContext) -> None:
        self.store.save_runtime(budget.snapshot().to_dict())

    def _record_failure(self, task: TaskSpec, call, result: ToolResult) -> None:
        failures = self.store.load_failure_history()
        signature = json.dumps({"tool": call.tool, "args": call.args}, sort_keys=True, ensure_ascii=False)
        existing = None
        for item in reversed(failures):
            if item.get("signature") == signature and item.get("task_id") == task.task_id:
                existing = item
                break
        if existing:
            existing["attempts"] = int(existing.get("attempts", 1)) + 1
            existing["reason"] = result.reason
            existing["evidence"] = result.evidence
        else:
            failures.append({"task_id": task.task_id, "signature": signature, "operation": call.tool, "args": call.args, "attempts": 1, "reason": result.reason, "evidence": result.evidence})
        self.store.save_failure_history(failures[-200:])

    def execute(self, task: TaskSpec) -> KeeperResult:
        budget = self._budget()
        surface = VerifiedToolSurface(self.bridge, budget)
        task.status = "running"
        self.store.save_task(task)

        initial = self.bridge.snapshot()
        if any(evaluate_condition(initial, cond) for cond in task.abort_if):
            task.status = "blocked"
            self.store.save_task(task)
            return KeeperResult("blocked", "abort condition already true", task)
        if task.success_when and all(evaluate_condition(initial, cond) for cond in task.success_when):
            task.status = "completed"
            self.store.save_task(task)
            self.watchdog.mark_meaningful_progress("task already satisfied")
            return KeeperResult("completed", "desired state already satisfied", task)

        while task.cursor < len(task.operations):
            call = task.operations[task.cursor]
            self.watchdog.record_action(call.tool, call.args)
            result = surface.call(call.tool, call.args)
            self._persist_budget(budget)
            self.action_log.append({"task_id": task.task_id, "tool": call.tool, "args": call.args, "result": result.to_dict()})

            if not result.ok:
                task.failures += 1
                task.status = "blocked"
                self._record_failure(task, call, result)
                self.store.save_task(task)
                return KeeperResult("blocked", result.reason, task, last_tool_result=result)

            if result.meaningful_progress:
                self.watchdog.mark_meaningful_progress(f"{call.tool} changed desired state")

            task.cursor += 1
            task.current_state = {"cursor": task.cursor, "last_tool": call.tool}
            task.remaining = {"operations": len(task.operations) - task.cursor}
            self.store.save_task(task)

            snap = self.bridge.snapshot()
            self.watchdog.record_state(snap)
            if any(evaluate_condition(snap, cond) for cond in task.abort_if):
                task.status = "blocked"
                self.store.save_task(task)
                return KeeperResult("blocked", "abort condition became true", task, last_tool_result=result)
            events = self.watchdog.evaluate()
            if events:
                task.status = "blocked"
                self.store.save_task(task)
                return KeeperResult("blocked", events[0].code, task, watchdog_events=events, last_tool_result=result)

        final = self.bridge.snapshot()
        if task.success_when and not all(evaluate_condition(final, cond) for cond in task.success_when):
            task.status = "blocked"
            self.store.save_task(task)
            return KeeperResult("blocked", "operations exhausted but success conditions are false", task)

        task.status = "completed"
        task.remaining = {"operations": 0}
        self.store.save_task(task)
        self.watchdog.mark_meaningful_progress("work item closed")
        return KeeperResult("completed", None, task)
