from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(slots=True)
class WatchdogConfig:
    no_progress_sec: float = 120.0
    action_history: int = 30
    state_history: int = 12
    recurrence_threshold: int = 4
    min_actions_for_loop: int = 6


@dataclass(slots=True)
class WatchdogEvent:
    code: str
    reason: str
    evidence: dict[str, Any]


class Watchdog:
    def __init__(self, config: WatchdogConfig | None = None, *, now=time.monotonic) -> None:
        self.config = config or WatchdogConfig()
        self._now = now
        self.last_meaningful_progress = now()
        self.actions: deque[str] = deque(maxlen=self.config.action_history)
        self.states: deque[str] = deque(maxlen=self.config.state_history)
        self.actions_since_progress = 0

    def progress_age(self) -> float:
        return max(0.0, self._now() - self.last_meaningful_progress)

    def mark_meaningful_progress(self, reason: str) -> None:
        self.last_meaningful_progress = self._now()
        self.actions_since_progress = 0

    def record_action(self, tool: str, args: Mapping[str, Any]) -> None:
        canonical = json.dumps({"tool": tool, "args": args}, sort_keys=True, ensure_ascii=False, default=str)
        self.actions.append(canonical)
        self.actions_since_progress += 1

    def record_state(self, snapshot: Mapping[str, Any]) -> None:
        research = snapshot.get("research") or {}
        power = snapshot.get("power") or {}
        resources = snapshot.get("resources") or {}
        core = {"research": {"technology": research.get("technology"), "progress": research.get("progress"), "state": research.get("state"), "science_supply": research.get("science_supply")}, "power": {"margin": power.get("margin"), "status": power.get("status")}, "resources": resources, "entity_count": len(snapshot.get("entities", []) or [])}
        raw = json.dumps(core, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        self.states.append(hashlib.sha256(raw).hexdigest())

    def _loop_event(self) -> WatchdogEvent | None:
        seq = list(self.actions)
        if len(seq) < self.config.min_actions_for_loop:
            return None
        for width in (1, 2, 3):
            need = width * 3
            if len(seq) < need:
                continue
            tail = seq[-need:]
            unit = tail[:width]
            if tail == unit * 3:
                return WatchdogEvent("LOOP_DETECTED", f"repeating action pattern of width {width}", {"pattern": unit, "repetitions": 3})
        return None

    def _recurrence_event(self) -> WatchdogEvent | None:
        if self.actions_since_progress < self.config.recurrence_threshold:
            return None
        if len(self.states) < self.config.recurrence_threshold:
            return None
        tail = list(self.states)[-self.config.recurrence_threshold:]
        if len(set(tail)) == 1:
            return WatchdogEvent("STATE_RECURRENCE", "key game state repeated without meaningful progress", {"fingerprint": tail[0], "count": len(tail)})
        return None

    def evaluate(self) -> list[WatchdogEvent]:
        events: list[WatchdogEvent] = []
        if self.progress_age() > self.config.no_progress_sec:
            events.append(WatchdogEvent("NO_PROGRESS", "meaningful progress timeout exceeded", {"age_sec": self.progress_age(), "limit_sec": self.config.no_progress_sec}))
        loop = self._loop_event()
        if loop:
            events.append(loop)
        recurrence = self._recurrence_event()
        if recurrence:
            events.append(recurrence)
        return events
