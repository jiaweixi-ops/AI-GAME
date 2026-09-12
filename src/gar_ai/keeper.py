from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Mapping

from .budget import AtomicBudgetLimits, BudgetContext, TaskBudgetLimits
from .storage import JsonStateStore
from .types import Condition, TaskSpec, ToolResult
from .verified_tools import VerifiedToolSurface
from .watchdog import Watchdog, WatchdogEvent

_MISSING = object()


def _resolve_path(root: Mapping[str, Any], path: str) -> Any:
    cur: Any = root
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


def evaluate_condition(
    root: Mapping[str, Any],
    condition: Condition,
    *,
    baseline: Mapping[str, Any] | None = None,
    missing_is_true: bool = False,
) -> bool:
    actual = _resolve_path(root, condition.path)
    if actual is _MISSING:
        return missing_is_true

    expected = condition.value
    op = condition.op

    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "truthy":
        return bool(actual)
    if op == "falsy":
        return not bool(actual)
    if op == "contains":
        try:
            return expected in actual
        except TypeError:
            return False

    before = (
        _resolve_path(baseline or {}, condition.path)
        if baseline is not None
        else _MISSING
    )

    if op == "changed":
        return before is not _MISSING and actual != before
    if op == "increased":
        try:
            return before is not _MISSING and actual > before
        except TypeError:
            return False
    if op == "delta_gt":
        try:
            return before is not _MISSING and (actual - before) > expected
        except TypeError:
            return False

    try:
        if op == "gt":
            return actual > expected
        if op == "gte":
            return actual >= expected
        if op == "lt":
            return actual < expected
        if op == "lte":
            return actual <= expected
    except TypeError:
        return False

    return False


def desired_state_view(
    snapshot: Mapping[str, Any],
    desired_state: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    current: dict[str, Any] = {}
    remaining: dict[str, Any] = {}

    for path, expected in desired_state.items():
        actual = _resolve_path(snapshot, path)
        current[path] = None if actual is _MISSING else actual
        if actual is _MISSING or actual != expected:
            remaining[path] = expected

    return current, remaining


@dataclass(slots=True)
class KeeperPolicy:
    atomic: AtomicBudgetLimits = field(
        default_factory=lambda: AtomicBudgetLimits(max_total_actions=100)
    )
    task: TaskBudgetLimits = field(
        default_factory=lambda: TaskBudgetLimits(
            max_actions=100,
            max_entities=32,
            max_material_cost=1000,
            max_duration_sec=300,
            max_failures=5,
            max_replans=2,
        )
    )
    action_log_limit: int = 500


@dataclass(slots=True)
class KeeperResult:
    status: str
    reason: str | None
    task: TaskSpec
    error_code: str | None = None
    watchdog_events: list[WatchdogEvent] = field(default_factory=list)
    last_tool_result: ToolResult | None = None


class Keeper:
    def __init__(
        self,
        bridge,
        store: JsonStateStore,
        watchdog: Watchdog,
        policy: KeeperPolicy | None = None,
    ) -> None:
        self.bridge = bridge
        self.store = store
        self.watchdog = watchdog
        self.policy = policy or KeeperPolicy()

        if self.policy.action_log_limit <= 0:
            raise ValueError("action_log_limit must be > 0")

        self.action_log: deque[dict[str, Any]] = deque(
            maxlen=self.policy.action_log_limit
        )

    def _append_action(self, entry: dict[str, Any]) -> None:
        self.action_log.append(entry)
        self.store.append_action(entry)

    def _budget(self, task: TaskSpec) -> BudgetContext:
        return BudgetContext(
            self.policy.atomic,
            self.policy.task,
            task_id=task.task_id,
            restored=self.store.load_runtime(),
            initial_replans=task.replans,
        )

    def _persist_budget(self, budget: BudgetContext) -> None:
        self.store.save_runtime(budget.snapshot().to_dict())

    def record_replan(self, task: TaskSpec) -> None:
        budget = self._budget(task)
        budget.record_replan()
        task.replans = budget.replans
        self._persist_budget(budget)
        self.store.save_task(task)

    def _record_failure(self, task: TaskSpec, call, result: ToolResult) -> None:
        failures = self.store.load_failure_history()
        signature = json.dumps(
            {"tool": call.tool, "args": call.args},
            sort_keys=True,
            ensure_ascii=False,
        )
        existing = None

        for item in reversed(failures):
            if (
                item.get("signature") == signature
                and item.get("task_id") == task.task_id
            ):
                existing = item
                break

        if existing:
            existing["attempts"] = int(existing.get("attempts", 1)) + 1
            existing["reason"] = result.reason
            existing["error_code"] = result.error_code
            existing["evidence"] = result.evidence
        else:
            failures.append(
                {
                    "task_id": task.task_id,
                    "signature": signature,
                    "operation": call.tool,
                    "args": call.args,
                    "attempts": 1,
                    "reason": result.reason,
                    "error_code": result.error_code,
                    "evidence": result.evidence,
                }
            )

        self.store.save_failure_history(failures[-200:])

    def execute(self, task: TaskSpec) -> KeeperResult:
        self.watchdog.begin_task(task.task_id)

        if not task.success_when:
            task.status = "blocked"
            self.store.save_task(task)
            return KeeperResult(
                "blocked",
                "task has no verifiable success conditions",
                task,
                error_code="INVALID_TASK",
            )

        budget = self._budget(task)
        surface = VerifiedToolSurface(self.bridge, budget)
        task.status = "running"
        self.store.save_task(task)

        initial = self.bridge.snapshot()
        baseline = initial

        for cond in task.abort_if:
            if _resolve_path(initial, cond.path) is _MISSING:
                task.status = "blocked"
                self.store.save_task(task)
                return KeeperResult(
                    "blocked",
                    f"abort_if path is unknown: {cond.path}",
                    task,
                    error_code="ABORT_CONDITION_UNKNOWN",
                )
            if evaluate_condition(
                initial,
                cond,
                baseline=baseline,
                missing_is_true=True,
            ):
                task.status = "blocked"
                self.store.save_task(task)
                return KeeperResult(
                    "blocked",
                    "abort condition already true",
                    task,
                    error_code="ABORT_CONDITION",
                )

        task.current_state, task.remaining = desired_state_view(
            initial,
            task.desired_state,
        )

        if all(
            evaluate_condition(initial, cond, baseline=baseline)
            for cond in task.success_when
        ):
            task.status = "completed"
            task.cursor = len(task.operations)
            self.store.save_task(task)
            return KeeperResult(
                "completed",
                "desired state already satisfied",
                task,
            )

        task.cursor = 0
        self.store.save_task(task)

        while task.cursor < len(task.operations):
            call = task.operations[task.cursor]
            self.watchdog.record_action(call.tool, call.args)

            result = surface.call(call.tool, call.args)
            self._persist_budget(budget)

            self._append_action(
                {
                    "task_id": task.task_id,
                    "tool": call.tool,
                    "args": call.args,
                    "result": result.to_dict(),
                }
            )

            if not result.ok:
                task.failures += 1
                task.status = "blocked"
                self._record_failure(task, call, result)
                self.store.save_task(task)
                return KeeperResult(
                    "blocked",
                    result.reason,
                    task,
                    error_code=result.error_code,
                    last_tool_result=result,
                )

            if result.meaningful_progress:
                self.watchdog.mark_meaningful_progress(
                    f"{call.tool} changed desired state"
                )

            task.cursor += 1
            snap = self.bridge.snapshot()
            task.current_state, task.remaining = desired_state_view(
                snap,
                task.desired_state,
            )
            self.store.save_task(task)

            for cond in task.abort_if:
                if _resolve_path(snap, cond.path) is _MISSING:
                    task.status = "blocked"
                    self.store.save_task(task)
                    return KeeperResult(
                        "blocked",
                        f"abort_if path is unknown: {cond.path}",
                        task,
                        error_code="ABORT_CONDITION_UNKNOWN",
                        last_tool_result=result,
                    )
                if evaluate_condition(
                    snap,
                    cond,
                    baseline=baseline,
                    missing_is_true=True,
                ):
                    task.status = "blocked"
                    self.store.save_task(task)
                    return KeeperResult(
                        "blocked",
                        "abort condition became true",
                        task,
                        error_code="ABORT_CONDITION",
                        last_tool_result=result,
                    )

            self.watchdog.record_state(snap)
            events = self.watchdog.evaluate()
            if events:
                task.status = "blocked"
                self.store.save_task(task)
                return KeeperResult(
                    "blocked",
                    events[0].code,
                    task,
                    error_code=events[0].code,
                    watchdog_events=events,
                    last_tool_result=result,
                )

        final = self.bridge.snapshot()
        if not all(
            evaluate_condition(final, cond, baseline=baseline)
            for cond in task.success_when
        ):
            task.status = "blocked"
            self.store.save_task(task)
            return KeeperResult(
                "blocked",
                "operations exhausted but success conditions are false",
                task,
                error_code="SUCCESS_CONDITION_FALSE",
            )

        task.status = "completed"
        task.current_state, task.remaining = desired_state_view(
            final,
            task.desired_state,
        )
        self.store.save_task(task)
        self.watchdog.mark_meaningful_progress("work item closed")
        return KeeperResult("completed", None, task)
