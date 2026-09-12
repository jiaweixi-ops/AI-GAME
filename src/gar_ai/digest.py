from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .types import MasterPlan


def _resource_view(snapshot: Mapping[str, Any], name: str) -> dict[str, Any]:
    raw = (snapshot.get("resources") or {}).get(name)
    if isinstance(raw, Mapping):
        return {"stock": raw.get("stock"), "rate": raw.get("rate")}
    if raw is None:
        return {"stock": None, "rate": None}
    return {"stock": raw, "rate": None}


class StateDigestBuilder:
    SCHEMA_VERSION = "v0.1"

    def build(self, snapshot: Mapping[str, Any], *, goal: str | None, agent_state: Mapping[str, Any] | None = None, recent_failure: Mapping[str, Any] | None = None, plan: MasterPlan | None = None) -> dict[str, Any]:
        agent_state = agent_state or {}
        research = snapshot.get("research") if isinstance(snapshot.get("research"), Mapping) else {}
        power = snapshot.get("power") if isinstance(snapshot.get("power"), Mapping) else {}
        threat = snapshot.get("threat") if isinstance(snapshot.get("threat"), Mapping) else {}
        failure = recent_failure or {}
        plan = plan or MasterPlan()
        bottleneck = snapshot.get("bottleneck")
        if bottleneck is None and research.get("state") == "starved":
            bottleneck = "research_starved"
        return {"schema_version": self.SCHEMA_VERSION, "generated_at": datetime.now(timezone.utc).isoformat(), "game_tick": snapshot.get("game_tick"), "goal": goal, "agent": {"task_id": agent_state.get("task_id"), "task_status": agent_state.get("task_status", "idle"), "task_progress": agent_state.get("task_progress", 0.0), "meaningful_progress_age_sec": agent_state.get("meaningful_progress_age_sec"), "mode": agent_state.get("mode", "normal")}, "power": {"margin": power.get("margin"), "status": power.get("status")}, "resources": {"iron": _resource_view(snapshot, "iron"), "copper": _resource_view(snapshot, "copper"), "coal": _resource_view(snapshot, "coal")}, "research": {"technology": research.get("technology"), "progress": research.get("progress"), "unit_count": research.get("unit_count"), "science_supply": research.get("science_supply"), "state": research.get("state")}, "bottleneck": bottleneck, "recent_failure": {"task_id": failure.get("task_id"), "reason": failure.get("reason"), "attempts": int(failure.get("attempts", 0) or 0), "evidence": failure.get("evidence")}, "threat": {"level": threat.get("level")}, "plan": {"current": plan.current, "next": plan.next, "watch": list(plan.watch)}}
