from __future__ import annotations

import math
from typing import Any, Callable

from .bridge import GameBridge
from .budget import BudgetContext, BudgetExceeded
from .digest import StateDigestBuilder
from .types import MasterPlan, ToolOutcome, ToolResult


def _inventory_count(snapshot: dict[str, Any], item: str) -> int:
    return int(snapshot.get("player", {}).get("inventory", {}).get(item, 0) or 0)


def _entity_at(snapshot: dict[str, Any], name: str | None, x: float, y: float, *, tolerance: float = 0.25) -> dict[str, Any] | None:
    for entity in snapshot.get("entities", []) or []:
        ex, ey = entity.get("position", [None, None])
        if ex is None or ey is None:
            continue
        if math.dist((float(ex), float(ey)), (x, y)) <= tolerance and (name is None or entity.get("name") == name):
            return entity
    return None


def _science_total(research: dict[str, Any]) -> float:
    supply = research.get("science_supply") or {}
    if not isinstance(supply, dict):
        return 0.0
    total = 0.0
    for value in supply.values():
        try:
            total += float(value or 0)
        except (TypeError, ValueError):
            pass
    return total


class VerifiedToolSurface:
    TOOL_NAMES = ("get_digest", "scan_area", "query_recipe", "query_technology", "move_to_verified", "ensure_item_verified", "place_verified", "transfer_verified", "set_recipe_verified", "research_verified")

    def __init__(self, bridge: GameBridge, budget: BudgetContext) -> None:
        self.bridge = bridge
        self.budget = budget

    def call(self, tool: str, args: dict[str, Any]) -> ToolResult:
        if tool not in self.TOOL_NAMES:
            return ToolResult(tool, ToolOutcome.BLOCKED, False, False, reason="tool not allowed", error_code="TOOL_NOT_ALLOWED")
        method = getattr(self, tool)
        try:
            return method(**args)
        except BudgetExceeded as exc:
            return ToolResult(tool, ToolOutcome.BLOCKED, False, False, reason=exc.detail, error_code=exc.code)
        except (KeyError, TypeError, ValueError) as exc:
            return ToolResult(tool, ToolOutcome.BLOCKED, False, False, reason=f"invalid arguments: {exc}", error_code="INVALID_ARGUMENTS")
        except RuntimeError as exc:
            return ToolResult(tool, ToolOutcome.BLOCKED, False, False, reason=str(exc), error_code="BRIDGE_ERROR")

    def get_digest(self) -> ToolResult:
        self.budget.consume_atomic("get_digest")
        snap = self.bridge.snapshot()
        digest = StateDigestBuilder().build(snap, goal=None, agent_state=None, recent_failure=None, plan=MasterPlan())
        return ToolResult("get_digest", ToolOutcome.VERIFIED, False, False, evidence={"digest": digest})

    def scan_area(self, center: list[float] | tuple[float, float], radius: float) -> ToolResult:
        self.budget.consume_atomic("scan_area")
        if len(center) != 2 or radius <= 0:
            raise ValueError("center must have two coordinates and radius must be > 0")
        data = self.bridge.scan_area((float(center[0]), float(center[1])), float(radius))
        return ToolResult("scan_area", ToolOutcome.VERIFIED, False, False, evidence=data)

    def query_recipe(self, name: str) -> ToolResult:
        self.budget.consume_atomic("query_recipe")
        return ToolResult("query_recipe", ToolOutcome.VERIFIED, False, False, evidence={"recipe": self.bridge.query_recipe(name)})

    def query_technology(self, name: str) -> ToolResult:
        self.budget.consume_atomic("query_technology")
        return ToolResult("query_technology", ToolOutcome.VERIFIED, False, False, evidence={"technology": self.bridge.query_technology(name)})

    def _write(self, *, tool: str, action: str, params: dict[str, Any], already_satisfied: Callable[[dict[str, Any]], bool], verify: Callable[[dict[str, Any], dict[str, Any]], tuple[bool, dict[str, Any], bool]], entities: int = 0, material_cost: int = 0, before: dict[str, Any] | None = None) -> ToolResult:
        before = before or self.bridge.snapshot()
        if already_satisfied(before):
            return ToolResult(tool, ToolOutcome.NOOP, False, False, reason="desired state already satisfied")
        self.budget.consume_atomic(tool, entities=entities, material_cost=material_cost)
        ack = self.bridge.act(action, params)
        if not ack.accepted:
            self.budget.record_failure()
            return ToolResult(tool, ToolOutcome.BLOCKED, False, False, reason=f"ACK rejected: {ack.detail or ack.status}", error_code="ACK_REJECTED", before=before, evidence={"ack": {"status": ack.status, "action_id": ack.action_id, "detail": ack.detail}})
        after = self.bridge.snapshot()
        ok, evidence, meaningful = verify(before, after)
        if not ok:
            self.budget.record_failure()
            return ToolResult(tool, ToolOutcome.UNVERIFIED, False, False, reason="ACK accepted but fresh-state verification failed", error_code="FRESH_STATE_UNVERIFIED", before=before, after=after, evidence={"ack": {"status": ack.status, "action_id": ack.action_id}, **evidence})
        return ToolResult(tool, ToolOutcome.VERIFIED, True, meaningful, before=before, after=after, evidence={"ack": {"status": ack.status, "action_id": ack.action_id}, **evidence})

    def move_to_verified(self, x: float, y: float, tolerance: float = 0.25) -> ToolResult:
        x, y, tolerance = float(x), float(y), float(tolerance)
        def satisfied(s):
            pos = s.get("player", {}).get("position", [None, None])
            return None not in pos and math.dist((float(pos[0]), float(pos[1])), (x, y)) <= tolerance
        def verify(_b, a):
            pos = a.get("player", {}).get("position", [None, None])
            ok = None not in pos and math.dist((float(pos[0]), float(pos[1])), (x, y)) <= tolerance
            return ok, {"position": pos, "target": [x, y]}, False
        return self._write(tool="move_to_verified", action="move_to", params={"x": x, "y": y}, already_satisfied=satisfied, verify=verify)

    def ensure_item_verified(self, item: str, count: int) -> ToolResult:
        count = int(count)
        if count < 0:
            raise ValueError("count must be >= 0")
        before = self.bridge.snapshot()
        existing = _inventory_count(before, item)
        def satisfied(s): return _inventory_count(s, item) >= count
        def verify(b, a):
            bc = _inventory_count(b, item); ac = _inventory_count(a, item)
            return ac >= count, {"item": item, "before": bc, "after": ac, "target": count}, ac > bc
        return self._write(tool="ensure_item_verified", action="ensure_item", params={"item": item, "count": count}, already_satisfied=satisfied, verify=verify, material_cost=max(0, count - existing), before=before)

    def place_verified(self, name: str, x: float, y: float, direction: int | None = None, tolerance: float = 0.25) -> ToolResult:
        x, y, tolerance = float(x), float(y), float(tolerance)
        def satisfied(s): return _entity_at(s, name, x, y, tolerance=tolerance) is not None
        def verify(_b, a):
            entity = _entity_at(a, name, x, y, tolerance=tolerance)
            return entity is not None, {"entity": entity, "target": {"name": name, "position": [x, y], "tolerance": tolerance}}, entity is not None
        params = {"name": name, "x": x, "y": y}
        if direction is not None:
            params["direction"] = int(direction)
        return self._write(tool="place_verified", action="place_entity", params=params, already_satisfied=satisfied, verify=verify, entities=1, material_cost=1)

    def transfer_verified(self, item: str, x: float, y: float, target_count: int, tolerance: float = 0.25) -> ToolResult:
        x, y, target_count, tolerance = float(x), float(y), int(target_count), float(tolerance)
        if target_count < 0:
            raise ValueError("target_count must be >= 0")
        before = self.bridge.snapshot()
        def target_inventory(s):
            entity = _entity_at(s, None, x, y, tolerance=tolerance)
            return -1 if entity is None else int(entity.get("inventory", {}).get(item, 0) or 0)
        current = target_inventory(before)
        if current < 0:
            return ToolResult("transfer_verified", ToolOutcome.BLOCKED, False, False, reason="target entity missing", error_code="TARGET_MISSING")
        needed = max(0, target_count - current)
        def satisfied(s): return target_inventory(s) >= target_count
        def verify(b, a):
            bc = target_inventory(b); ac = target_inventory(a)
            return ac >= target_count, {"item": item, "target_count": target_count, "before": bc, "after": ac}, ac > bc
        return self._write(tool="transfer_verified", action="transfer", params={"item": item, "count": needed, "x": x, "y": y}, already_satisfied=satisfied, verify=verify, material_cost=needed, before=before)

    def set_recipe_verified(self, x: float, y: float, recipe: str, tolerance: float = 0.25) -> ToolResult:
        x, y, tolerance = float(x), float(y), float(tolerance)
        def recipe_at(s):
            entity = _entity_at(s, None, x, y, tolerance=tolerance)
            return entity.get("recipe") if entity else None
        def satisfied(s): return recipe_at(s) == recipe
        def verify(_b, a):
            actual = recipe_at(a)
            return actual == recipe, {"recipe": actual, "expected": recipe}, False
        return self._write(tool="set_recipe_verified", action="set_recipe", params={"x": x, "y": y, "recipe": recipe}, already_satisfied=satisfied, verify=verify)

    def research_verified(self, technology: str) -> ToolResult:
        def research(s): return s.get("research", {}) or {}
        def satisfied(s):
            r = research(s)
            return r.get("technology") == technology and r.get("state") == "progressing"
        def verify(b, a):
            rb, ra = research(b), research(a)
            selected = ra.get("technology") == technology
            before_progress = float(rb.get("progress", 0.0) or 0.0)
            after_progress = float(ra.get("progress", 0.0) or 0.0)
            state_advanced = rb.get("state") != "progressing" and ra.get("state") == "progressing"
            progress_advanced = after_progress > before_progress
            science_consumed = _science_total(ra) < _science_total(rb)
            ok = selected and (ra.get("state") == "progressing" or progress_advanced or science_consumed)
            return ok, {"technology": ra.get("technology"), "expected": technology, "state_before": rb.get("state"), "state_after": ra.get("state"), "progress_before": before_progress, "progress_after": after_progress, "proof": {"state_advanced": state_advanced, "progress_advanced": progress_advanced, "science_consumed": science_consumed}}, bool(state_advanced or progress_advanced or science_consumed)
        return self._write(tool="research_verified", action="start_research", params={"technology": technology}, already_satisfied=satisfied, verify=verify)
