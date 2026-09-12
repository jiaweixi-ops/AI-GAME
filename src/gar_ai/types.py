from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


class ToolOutcome(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    BLOCKED = "blocked"
    NOOP = "noop"


@dataclass(slots=True)
class Ack:
    status: str
    action_id: str | None = None
    detail: str | None = None

    @property
    def accepted(self) -> bool:
        return self.status.strip().lower() == "accepted"


@dataclass(slots=True)
class ToolResult:
    tool: str
    outcome: ToolOutcome
    changed: bool
    meaningful_progress: bool
    reason: str | None = None
    error_code: str | None = None
    before: Mapping[str, Any] | None = None
    after: Mapping[str, Any] | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.outcome in {ToolOutcome.VERIFIED, ToolOutcome.NOOP}

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["outcome"] = self.outcome.value
        return data


@dataclass(slots=True)
class ToolCall:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ToolCall":
        tool = data.get("tool")
        args = data.get("args", {})
        if not isinstance(tool, str) or not tool:
            raise ValueError("tool call requires non-empty 'tool'")
        if not isinstance(args, dict):
            raise ValueError("tool call 'args' must be an object")
        return cls(tool=tool, args=dict(args))


@dataclass(slots=True)
class Condition:
    path: str
    op: str
    value: Any = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Condition":
        path = data.get("path")
        op = data.get("op")
        if not isinstance(path, str) or not path:
            raise ValueError("condition.path must be a non-empty string")
        allowed = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "truthy", "falsy", "changed", "increased", "delta_gt"}
        if op not in allowed:
            raise ValueError(f"unsupported condition op: {op!r}")
        return cls(path=path, op=str(op), value=data.get("value"))


@dataclass(slots=True)
class TaskSpec:
    task_id: str
    objective: str
    reason: str
    desired_state: dict[str, Any]
    operations: list[ToolCall]
    success_when: list[Condition]
    abort_if: list[Condition]
    current_state: dict[str, Any] = field(default_factory=dict)
    remaining: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    cursor: int = 0
    failures: int = 0
    replans: int = 0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TaskSpec":
        task_id = data.get("task_id")
        objective = data.get("objective")
        reason = data.get("reason", "")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("task_id must be a non-empty string")
        if not isinstance(objective, str) or not objective:
            raise ValueError("objective must be a non-empty string")
        if not isinstance(reason, str):
            raise ValueError("reason must be a string")
        desired_state = data.get("desired_state", {})
        if not isinstance(desired_state, dict):
            raise ValueError("desired_state must be an object")
        operations_raw = data.get("operations", [])
        success_raw = data.get("success_when", [])
        abort_raw = data.get("abort_if", [])
        if not isinstance(operations_raw, list):
            raise ValueError("operations must be an array")
        if not isinstance(success_raw, list) or not isinstance(abort_raw, list):
            raise ValueError("success_when and abort_if must be arrays")
        return cls(task_id=task_id, objective=objective, reason=reason, desired_state=dict(desired_state), operations=[ToolCall.from_dict(x) for x in operations_raw], success_when=[Condition.from_dict(x) for x in success_raw], abort_if=[Condition.from_dict(x) for x in abort_raw], current_state=dict(data.get("current_state", {}) or {}), remaining=dict(data.get("remaining", {}) or {}), status=str(data.get("status", "pending")), cursor=int(data.get("cursor", 0)), failures=int(data.get("failures", 0)), replans=int(data.get("replans", 0)))

    def to_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "objective": self.objective, "reason": self.reason, "desired_state": self.desired_state, "operations": [asdict(x) for x in self.operations], "success_when": [asdict(x) for x in self.success_when], "abort_if": [asdict(x) for x in self.abort_if], "current_state": self.current_state, "remaining": self.remaining, "status": self.status, "cursor": self.cursor, "failures": self.failures, "replans": self.replans}


@dataclass(slots=True)
class MasterPlan:
    long_term: str | None = None
    mid_term: str | None = None
    current: str | None = None
    next: str | None = None
    watch: list[str] = field(default_factory=list)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MasterPlan":
        return cls(long_term=data.get("long_term"), mid_term=data.get("mid_term"), current=data.get("current"), next=data.get("next"), watch=list(data.get("watch", []) or []), version=int(data.get("version", 1)))


@dataclass(slots=True)
class Decision:
    decision: str
    task: TaskSpec | None = None
    plan_patch: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Decision":
        kind = data.get("decision")
        if kind not in {"create_task", "continue", "safe_stop"}:
            raise ValueError("decision must be create_task, continue, or safe_stop")
        task = None
        if kind == "create_task":
            raw = data.get("task")
            if not isinstance(raw, dict):
                raise ValueError("create_task requires task object")
            task = TaskSpec.from_dict(raw)
        patch = data.get("plan_patch", {}) or {}
        if not isinstance(patch, dict):
            raise ValueError("plan_patch must be an object")
        reason = data.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise ValueError("reason must be a string or null")
        return cls(decision=kind, task=task, plan_patch=dict(patch), reason=reason)
