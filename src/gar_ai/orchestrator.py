from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ai_client import AIClient
from .digest import StateDigestBuilder
from .incidents import IncidentManager
from .keeper import Keeper, KeeperResult
from .storage import JsonStateStore
from .types import Decision, MasterPlan
from .verified_tools import VerifiedToolSurface
from .watchdog import Watchdog


@dataclass(slots=True)
class OrchestratorResult:
    status: str
    trigger: str
    decision: Decision | None = None
    keeper: KeeperResult | None = None
    incident_path: str | None = None


class Orchestrator:
    """Event-driven V0 planner/executor loop. Keeper work is zero-token."""

    def __init__(self, *, bridge, ai: AIClient, store: JsonStateStore, incidents: IncidentManager, watchdog: Watchdog | None = None, goal: str = "advance the current game safely") -> None:
        self.bridge = bridge
        self.ai = ai
        self.store = store
        self.incidents = incidents
        self.watchdog = watchdog or Watchdog()
        self.goal = goal
        self.digest_builder = StateDigestBuilder()
        self.keeper = Keeper(bridge, store, self.watchdog)

    def _agent_state(self, task) -> dict[str, Any]:
        if task is None:
            return {"task_id": None, "task_status": "idle", "task_progress": 0.0, "meaningful_progress_age_sec": self.watchdog.progress_age(), "mode": "normal"}
        total = max(1, len(task.operations))
        return {"task_id": task.task_id, "task_status": task.status, "task_progress": min(1.0, task.cursor / total), "meaningful_progress_age_sec": self.watchdog.progress_age(), "mode": "normal" if task.status != "blocked" else "replan"}

    def _build_digest(self, task=None) -> dict[str, Any]:
        failures = self.store.load_failure_history()
        recent_failure = failures[-1] if failures else None
        return self.digest_builder.build(self.bridge.snapshot(), goal=self.goal, agent_state=self._agent_state(task), recent_failure=recent_failure, plan=self.store.load_plan())

    def _apply_plan_patch(self, plan: MasterPlan, patch: dict[str, Any], *, allow_current_change: bool) -> MasterPlan:
        old_current = plan.current
        for key in ("long_term", "mid_term", "next"):
            if key in patch:
                setattr(plan, key, patch[key])
        if "watch" in patch and isinstance(patch["watch"], list):
            plan.watch = [str(x) for x in patch["watch"]]
        if "current" in patch:
            requested = patch["current"]
            if allow_current_change or old_current in {None, requested}:
                plan.current = requested
        if patch:
            plan.version += 1
        self.store.save_plan(plan)
        return plan

    def _create_incident(self, reason: str, task) -> str:
        digest = self._build_digest(task)
        path = self.incidents.create(reason, digest=digest, task=task.to_dict() if task else None, master_plan=self.store.load_plan().to_dict(), actions=self.keeper.action_log[-100:], failures=self.store.load_failure_history()[-50:], nearby_state=None, budget=self.store.load_runtime())
        return str(path)

    def tick(self, *, trigger: str = "event") -> OrchestratorResult:
        task = self.store.load_task()
        if task is not None and task.status in {"pending", "running"}:
            keeper_result = self.keeper.execute(task)
            if keeper_result.status == "completed":
                self.store.clear_task()
                return OrchestratorResult("task_completed", trigger, keeper=keeper_result)
            incident = self._create_incident(keeper_result.reason or "blocked", task)
            task.status = "blocked"
            self.store.save_task(task)
            return OrchestratorResult("needs_replan", "task_blocked", keeper=keeper_result, incident_path=incident)

        if task is not None and task.status == "blocked" and trigger not in {"replan", "user_goal_change", "strategic_review"}:
            return OrchestratorResult("needs_replan", "task_blocked")

        digest = self._build_digest(task)
        failures = self.store.load_failure_history()
        plan = self.store.load_plan()
        decision = self.ai.decide(digest=digest, master_plan=plan.to_dict(), failure_history=failures, allowed_tools=list(VerifiedToolSurface.TOOL_NAMES), trigger=trigger)
        allow_current_change = task is None or task.status in {"blocked", "completed"} or trigger in {"replan", "user_goal_change"}
        self._apply_plan_patch(plan, decision.plan_patch, allow_current_change=allow_current_change)

        if decision.decision == "safe_stop":
            return OrchestratorResult("safe_stop", trigger, decision=decision)
        if decision.decision == "continue":
            return OrchestratorResult("continue", trigger, decision=decision)
        assert decision.task is not None
        self.store.clear_task()
        self.store.save_task(decision.task)
        keeper_result = self.keeper.execute(decision.task)
        if keeper_result.status == "completed":
            self.store.clear_task()
            return OrchestratorResult("task_completed", trigger, decision=decision, keeper=keeper_result)
        incident = self._create_incident(keeper_result.reason or "blocked", decision.task)
        return OrchestratorResult("needs_replan", "task_blocked", decision=decision, keeper=keeper_result, incident_path=incident)
