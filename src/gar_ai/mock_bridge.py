from __future__ import annotations

import copy
import math
import uuid
from typing import Any, Mapping

from .types import Ack


class InMemoryBridge:
    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self.state = state or {"game_tick": 1, "player": {"position": [0.0, 0.0], "inventory": {}}, "entities": [], "power": {"margin": 0.30, "status": "ok"}, "resources": {"iron": {"stock": 0, "rate": 0}, "copper": {"stock": 0, "rate": 0}, "coal": {"stock": 0, "rate": 0}}, "research": {"technology": None, "progress": 0.0, "unit_count": None, "science_supply": {}, "state": "idle"}, "threat": {"level": "low"}}
        self.recipes: dict[str, dict[str, Any]] = {}; self.technologies: dict[str, dict[str, Any]] = {}; self.reject_actions: set[str] = set(); self.accept_without_effect: set[str] = set(); self.round_positions_to: int | None = None
    def snapshot(self) -> dict[str, Any]: return copy.deepcopy(self.state)
    def scan_area(self, center: tuple[float, float], radius: float) -> dict[str, Any]:
        cx, cy = center; entities = []
        for e in self.state.get("entities", []):
            x, y = e.get("position", [0, 0])
            if math.dist((cx, cy), (x, y)) <= radius: entities.append(copy.deepcopy(e))
        return {"center": [cx, cy], "radius": radius, "entities": entities}
    def query_recipe(self, name: str) -> dict[str, Any] | None:
        value = self.recipes.get(name); return copy.deepcopy(value) if value is not None else None
    def query_technology(self, name: str) -> dict[str, Any] | None:
        value = self.technologies.get(name); return copy.deepcopy(value) if value is not None else None
    def _ack(self, action: str, accepted: bool, detail: str | None = None) -> Ack: return Ack(status="accepted" if accepted else "rejected", action_id=str(uuid.uuid4()), detail=detail)
    def act(self, action: str, params: Mapping[str, Any]) -> Ack:
        if action in self.reject_actions: return self._ack(action, False, "configured rejection")
        if action in self.accept_without_effect: return self._ack(action, True, "accepted without state mutation")
        self.state["game_tick"] = int(self.state.get("game_tick", 0)) + 1
        if action == "move_to": self.state["player"]["position"] = [float(params["x"]), float(params["y"])]; return self._ack(action, True)
        if action == "ensure_item":
            item, count = str(params["item"]), int(params["count"]); inv = self.state["player"].setdefault("inventory", {}); inv[item] = max(int(inv.get(item, 0)), count); return self._ack(action, True)
        if action == "place_entity":
            name = str(params["name"]); x, y = float(params["x"]), float(params["y"])
            if self.round_positions_to is not None: x, y = round(x, self.round_positions_to), round(y, self.round_positions_to)
            pos = [x, y]
            for e in self.state.get("entities", []):
                if e.get("name") == name and e.get("position") == pos: return self._ack(action, True, "already present")
            self.state.setdefault("entities", []).append({"name": name, "position": pos, "inventory": {}, "recipe": None}); return self._ack(action, True)
        if action == "transfer":
            item, count = str(params["item"]), int(params["count"]); x, y = float(params["x"]), float(params["y"]); player_inv = self.state["player"].setdefault("inventory", {}); available = int(player_inv.get(item, 0)); moved = min(available, count)
            if moved <= 0: return self._ack(action, False, "no source items")
            entity = self._entity_at(x, y)
            if entity is None: return self._ack(action, False, "target entity missing")
            player_inv[item] = available - moved; entity.setdefault("inventory", {})[item] = int(entity.setdefault("inventory", {}).get(item, 0)) + moved; research = self.state.get("research", {})
            if entity.get("name") == "lab" and item.endswith("science-pack") and research.get("technology"):
                research.setdefault("science_supply", {})[item] = int(research.setdefault("science_supply", {}).get(item, 0)) + moved; research["state"] = "progressing"; research["progress"] = min(1.0, float(research.get("progress", 0.0)) + 0.01 * moved)
            return self._ack(action, True)
        if action == "set_recipe":
            entity = self._entity_at(float(params["x"]), float(params["y"]))
            if entity is None: return self._ack(action, False, "target entity missing")
            entity["recipe"] = str(params["recipe"]); return self._ack(action, True)
        if action == "start_research":
            technology = str(params["technology"]); self.state["research"]["technology"] = technology; self.state["research"]["state"] = "progressing" if self.state["research"].get("science_supply") else "starved"; return self._ack(action, True)
        return self._ack(action, False, f"unsupported action: {action}")
    def _entity_at(self, x: float, y: float) -> dict[str, Any] | None:
        for entity in self.state.get("entities", []):
            ex, ey = entity.get("position", [None, None])
            if ex is not None and ey is not None and math.dist((float(ex), float(ey)), (x, y)) <= 0.25: return entity
        return None
