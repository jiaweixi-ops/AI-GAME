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
    """Long-lived driver for the event-driven agent.

    Runtime safety semantics live in :meth:`step`, not only in
    :meth:`run_forever`. Any caller that drives the controller one step at a
    time therefore gets the same SAFE_HOLD behavior as the built-in loop.
    """

    def __init__(
        self,
        orchestrator: Orchestrator,
        config: ControllerConfig | None = None,
        *,
        now=time.monotonic,
        sleep=time.sleep,
    ) -> None:
        self.orchestrator = orchestrator
        self.config = config or ControllerConfig()
        self._now = now
        self._sleep = sleep
        self._last_review = now()
        self._started = False
        self._safe_hold = False
        self._safe_hold_reason: str | None = None
        self._resume_pending = False

    @property
    def safe_hold(self) -> bool:
        return self._safe_hold

    @property
    def safe_hold_reason(self) -> str | None:
        return self._safe_hold_reason

    def enter_safe_hold(self, reason: str | None = None) -> None:
        self._safe_hold = True
        self._safe_hold_reason = reason or "safe_stop"
        logger.warning("controller entered SAFE_HOLD: %s", self._safe_hold_reason)

    def resume(self) -> None:
        """Leave SAFE_HOLD and force a fresh user-resume synchronization."""
        self._safe_hold = False
        self._safe_hold_reason = None
        self._resume_pending = True
        logger.info("controller resume requested")

    def _finalize_result(self, result: OrchestratorResult) -> OrchestratorResult:
        """Apply runtime safety transitions to every externally visible step."""
        if result.status == "safe_stop":
            self.enter_safe_hold(result.trigger)
        return result

    def step(self) -> OrchestratorResult:
        if self._safe_hold:
            return OrchestratorResult("safe_hold", "heartbeat")

        if self._resume_pending:
            self._resume_pending = False
            return self._finalize_result(
                self.orchestrator.tick(trigger="user_resume")
            )

        task = self.orchestrator.store.load_task()

        if not self._started:
            self._started = True
            return self._finalize_result(
                self.orchestrator.tick(trigger="startup")
            )

        if task is not None:
            return self._finalize_result(
                self.orchestrator.tick(trigger="heartbeat")
            )

        if self._now() - self._last_review >= self.config.strategic_review_sec:
            self._last_review = self._now()
            return self._finalize_result(
                self.orchestrator.tick(trigger="strategic_review")
            )

        return OrchestratorResult("idle", "heartbeat")

    def shutdown(self) -> None:
        """Flush runtime state owned by the orchestrator/store before exit."""
        flush = getattr(self.orchestrator, "flush_runtime", None)
        if callable(flush):
            flush()

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        stop_event = stop_event or threading.Event()
        try:
            while not stop_event.is_set():
                result = self.step()
                logger.info(
                    "controller status=%s trigger=%s",
                    result.status,
                    result.trigger,
                )
                stop_event.wait(self.config.heartbeat_sec)
        finally:
            self.shutdown()
