from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .ai_client import AIClient
from .budget import BudgetExceeded
from .digest import StateDigestBuilder
from .incidents import IncidentManager
from .keeper import Keeper, KeeperPolicy, KeeperResult
from .storage import JsonStateStore
from .types import Decision, MasterPlan, TaskSpec
from .verified_tools import VerifiedToolSurface
from .watchdog import Watchdog

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OrchestratorResult:
    status: str
    trigger: str
    decision: Decision | None = None
    keeper: KeeperResult | None = None
    incident_path: str | None = None
    reason: str | None = None


class Orchestrator:
    def __init__(
        self,
        *,
        bridge,
        ai: AIClient,
        store: JsonStateStore,
        incidents: IncidentManager,
        watchdog: Watchdog | None = None,
        keeper_policy: KeeperPolicy | None = None,
        goal: str = "advance the current game safely",
    ) -> None:
        self.bridge = bridge
        self.ai = ai
        self.store = store
        self.incidents = incidents
        self.watchdog = watchdog or Watchdog()
        self.goal = goal
        self.digest_builder = StateDigestBuilder()
        self.keeper = Keeper(
            bridge,
            store,
            self.watchdog,
            policy=keeper_policy,
        )

    def flush_runtime(self) -> None:
        """Flush store-owned buffered state when the controller shuts down."""
        flush = getattr(self.store, "flush", None)
        if callable(flush):
            flush()

    def _agent_state(self, task: TaskSpec | None) -> dict[str, Any]:
        if task is None:
            return {
                "task_id": None,
                "task_status": "idle",
                "task_progress": 0.0,
                "meaningful_progress_age_sec": self.watchdog.progress_age(),
                "mode": "normal",
            }

        total = max(1, len(task.operations))
        return {
            "task_id": task.task_id,
            "task_status": task.status,
            "task_progress": min(1.0, task.cursor / total),
            "meaningful_progress_age_sec": self.watchdog.progress_age(),
            "mode": "normal" if task.status != "blocked" else "replan",
        }

    def _build_digest(self, task: TaskSpec | None = None) -> dict[str, Any]:
        failures = self.store.load_failure_history()
        recent_failure = failures[-1] if failures else None
        return self.digest_builder.build(
            self.bridge.snapshot(),
            goal=self.goal,
            agent_state=self._agent_state(task),
            recent_failure=recent_failure,
            plan=self.store.load_plan(),
        )

    def _apply_plan_patch(
        self,
        plan: MasterPlan,
        patch: dict[str, Any],
        *,
        allow_current_change: bool,
    ) -> MasterPlan:
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

    def _create_incident(self, reason: str, task: TaskSpec | None) -> str:
        path = self.incidents.create(
            reason,
            digest=self._build_digest(task),
            task=task.to_dict() if task else None,
            master_plan=self.store.load_plan().to_dict(),
            actions=list(self.keeper.action_log)[-100:],
            failures=self.store.load_failure_history()[-50:],
            nearby_state=None,
            budget=self.store.load_runtime(),
        )
        self.store.increment_metric("incidents")
        return str(path)

    def _ask_ai(
        self,
        *,
        trigger: str,
        task: TaskSpec | None,
    ) -> Decision | None:
        try:
            self.store.increment_metric("ai_calls")
            return self.ai.decide(
                digest=self._build_digest(task),
                master_plan=self.store.load_plan().to_dict(),
                failure_history=self.store.load_failure_history(),
                allowed_tools=list(VerifiedToolSurface.TOOL_NAMES),
                trigger=trigger,
            )
        except Exception as exc:
            logger.exception("AI decision failed; entering safe hold")
            self._create_incident(f"ai_error_{type(exc).__name__}", task)
            self.store.increment_metric("safe_stops")
            return None

    def _install_and_run_task(
        self,
        decision: Decision,
        *,
        trigger: str,
        previous_task: TaskSpec | None = None,
    ) -> OrchestratorResult:
        assert decision.task is not None

        if previous_task is not None:
            decision.task.replans = previous_task.replans

        self.store.clear_task()
        self.store.save_task(decision.task)
        keeper_result = self.keeper.execute(decision.task)

        if keeper_result.status == "completed":
            self.store.clear_task()
            return OrchestratorResult(
                "task_completed",
                trigger,
                decision=decision,
                keeper=keeper_result,
            )

        incident_reason = (
            keeper_result.error_code or keeper_result.reason or "blocked"
        )
        incident = self._create_incident(incident_reason, decision.task)
        decision.task.status = "blocked"
        self.store.save_task(decision.task)

        if trigger != "replan":
            replanned = self._replan_blocked(decision.task)
            if replanned.incident_path is None:
                replanned.incident_path = incident
            return replanned

        return OrchestratorResult(
            "needs_replan",
            "task_blocked",
            decision=decision,
            keeper=keeper_result,
            incident_path=incident,
            reason=incident_reason,
        )

    def _replan_blocked(self, task: TaskSpec) -> OrchestratorResult:
        try:
            self.keeper.record_replan(task)
            self.store.increment_metric("replans")
        except BudgetExceeded as exc:
            incident = self._create_incident(exc.code, task)
            self.store.increment_metric("safe_stops")
            return OrchestratorResult(
                "safe_stop",
                "replan",
                incident_path=incident,
                reason=exc.code,
            )

        decision = self._ask_ai(trigger="replan", task=task)
        if decision is None:
            return OrchestratorResult(
                "safe_stop",
                "replan",
                reason="ai_error",
            )

        self._apply_plan_patch(
            self.store.load_plan(),
            decision.plan_patch,
            allow_current_change=True,
        )

        if decision.decision == "safe_stop":
            self.store.increment_metric("safe_stops")
            return OrchestratorResult(
                "safe_stop",
                "replan",
                decision=decision,
                reason=decision.reason or "model_safe_stop",
            )

        if decision.decision == "continue":
            return OrchestratorResult(
                "needs_replan",
                "replan_returned_continue",
                decision=decision,
            )

        return self._install_and_run_task(
            decision,
            trigger="replan",
            previous_task=task,
        )

    def tick(self, *, trigger: str = "event") -> OrchestratorResult:
        task = self.store.load_task()

        if task is not None and task.status in {"pending", "running"}:
            keeper_result = self.keeper.execute(task)
            if keeper_result.status == "completed":
                self.store.clear_task()
                return OrchestratorResult(
                    "task_completed",
                    trigger,
                    keeper=keeper_result,
                )

            incident_reason = keeper_result.error_code or keeper_result.reason or "blocked"
            incident = self._create_incident(incident_reason, task)
            task.status = "blocked"
            self.store.save_task(task)

            replanned = self._replan_blocked(task)
            if replanned.incident_path is None:
                replanned.incident_path = incident
            if replanned.reason is None:
                replanned.reason = incident_reason
            return replanned

        if task is not None and task.status == "blocked":
            return self._replan_blocked(task)

        decision = self._ask_ai(trigger=trigger, task=task)
        if decision is None:
            return OrchestratorResult(
                "safe_stop",
                trigger,
                reason="ai_error",
            )

        self._apply_plan_patch(
            self.store.load_plan(),
            decision.plan_patch,
            allow_current_change=(
                task is None
                or trigger in {"replan", "user_goal_change", "user_resume"}
            ),
        )

        if decision.decision == "safe_stop":
            self.store.increment_metric("safe_stops")
            return OrchestratorResult(
                "safe_stop",
                trigger,
                decision=decision,
                reason=decision.reason or "model_safe_stop",
            )

        if decision.decision == "continue":
            return OrchestratorResult(
                "continue",
                trigger,
                decision=decision,
            )

        return self._install_and_run_task(
            decision,
            trigger=trigger,
            previous_task=task,
        )
