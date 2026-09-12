from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from .orchestrator import Orchestrator, OrchestratorResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ControllerConfig:
    heartbeat_sec: float = 1.0
    strategic_review_sec: float = 180.0


class ControllerLoop:
    def __init__(self, orchestrator: Orchestrator, config: ControllerConfig | None = None, *, now=time.monotonic, sleep=time.sleep) -> None:
        self.orchestrator = orchestrator; self.config = config or ControllerConfig(); self._now = now; self._sleep = sleep; self._last_review = now(); self._started = False

    def step(self) -> OrchestratorResult:
        task = self.orchestrator.store.load_task()
        if not self._started:
            self._started = True; return self.orchestrator.tick(trigger="startup")
        if task is not None: return self.orchestrator.tick(trigger="heartbeat")
        if self._now() - self._last_review >= self.config.strategic_review_sec:
            self._last_review = self._now(); return self.orchestrator.tick(trigger="strategic_review")
        return OrchestratorResult("idle", "heartbeat")

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        stop_event = stop_event or threading.Event()
        while not stop_event.is_set():
            result = self.step(); logger.info("controller status=%s trigger=%s", result.status, result.trigger)
            if result.status == "safe_stop": return
            stop_event.wait(self.config.heartbeat_sec)
