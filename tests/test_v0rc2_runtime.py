import signal
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from gar_ai.ai_client import ScriptedAIClient
from gar_ai.batch_budget import (
    BatchBudgetContext,
    GlobalBudgetLimits,
    GlobalBudgetPersistencePolicy,
)
from gar_ai.budget import AtomicBudgetLimits, BudgetContext, TaskBudgetLimits
from gar_ai.cli import install_signal_handlers
from gar_ai.controller import ControllerLoop
from gar_ai.incidents import IncidentManager
from gar_ai.keeper import KeeperPolicy
from gar_ai.mock_bridge import InMemoryBridge
from gar_ai.orchestrator import Orchestrator, OrchestratorResult
from gar_ai.storage import JsonStateStore


class _Store:
    def load_task(self):
        return None


class _TwoStageOrchestrator:
    def __init__(self):
        self.store = _Store()
        self.calls = []

    def tick(self, *, trigger="event"):
        self.calls.append(trigger)
        if trigger == "startup":
            return OrchestratorResult("safe_stop", "ai_error")
        return OrchestratorResult("continue", trigger)


class _CountingGlobalStore:
    def __init__(self):
        self.data = {}
        self.saves = 0

    def load_global_budget(self):
        return dict(self.data)

    def save_global_budget(self, data):
        self.data = dict(data)
        self.saves += 1


class V0RC2RuntimeTests(unittest.TestCase):
    def test_step_itself_enters_safe_hold(self):
        orchestrator = _TwoStageOrchestrator()
        loop = ControllerLoop(orchestrator)

        first = loop.step()
        second = loop.step()

        self.assertEqual(first.status, "safe_stop")
        self.assertTrue(loop.safe_hold)
        self.assertEqual(loop.safe_hold_reason, "ai_error")
        self.assertEqual(second.status, "safe_hold")
        self.assertEqual(orchestrator.calls, ["startup"])

    def test_resume_is_bidirectional_and_forces_user_resume(self):
        orchestrator = _TwoStageOrchestrator()
        loop = ControllerLoop(orchestrator)
        loop.step()
        self.assertTrue(loop.safe_hold)

        loop.resume()
        result = loop.step()

        self.assertFalse(loop.safe_hold)
        self.assertEqual(result.status, "continue")
        self.assertEqual(result.trigger, "user_resume")
        self.assertEqual(orchestrator.calls, ["startup", "user_resume"])

    def test_signal_paths_keep_resume_separate_from_shutdown(self):
        orchestrator = _TwoStageOrchestrator()
        loop = ControllerLoop(orchestrator)
        stop = threading.Event()
        captured = {}

        def capture(sig, handler):
            captured[sig] = handler

        with patch("gar_ai.cli.signal.signal", side_effect=capture):
            resume_names = install_signal_handlers(loop, stop)

        self.assertIn(signal.SIGINT, captured)
        captured[signal.SIGINT](signal.SIGINT, None)
        self.assertTrue(stop.is_set())

        if hasattr(signal, "SIGUSR1"):
            self.assertIn("SIGUSR1", resume_names)
            loop.enter_safe_hold("test")
            captured[signal.SIGUSR1](signal.SIGUSR1, None)
            self.assertFalse(loop.safe_hold)

    def test_global_budget_persistence_is_batched_and_force_flushable(self):
        store = _CountingGlobalStore()
        now = [0.0]
        parent = BudgetContext(
            AtomicBudgetLimits(20),
            TaskBudgetLimits(
                max_actions=20,
                max_entities=20,
                max_material_cost=20,
            ),
            task_id="t",
        )
        budget = BatchBudgetContext(
            parent,
            batch_id="b",
            global_limits=GlobalBudgetLimits(
                max_actions=20,
                max_entities=20,
                max_material_cost=20,
                window_sec=3600,
            ),
            global_store=store,
            persistence=GlobalBudgetPersistencePolicy(
                flush_every_actions=3,
                flush_interval_sec=999,
            ),
            clock=lambda: now[0],
        )

        budget.consume_atomic("x")
        budget.consume_atomic("x")
        self.assertEqual(store.saves, 0)

        budget.consume_atomic("x")
        self.assertEqual(store.saves, 1)
        self.assertEqual(store.data["actions"], 3)

        budget.consume_atomic("x")
        self.assertEqual(store.saves, 1)
        budget.flush_global()
        self.assertEqual(store.saves, 2)
        self.assertEqual(store.data["actions"], 4)

    def test_global_budget_time_threshold_flushes(self):
        store = _CountingGlobalStore()
        now = [0.0]
        parent = BudgetContext(
            AtomicBudgetLimits(20),
            TaskBudgetLimits(
                max_actions=20,
                max_entities=20,
                max_material_cost=20,
            ),
            task_id="t",
        )
        budget = BatchBudgetContext(
            parent,
            batch_id="b",
            global_store=store,
            persistence=GlobalBudgetPersistencePolicy(
                flush_every_actions=100,
                flush_interval_sec=5,
            ),
            clock=lambda: now[0],
        )

        budget.consume_atomic("x")
        self.assertEqual(store.saves, 0)
        now[0] = 6.0
        budget.consume_atomic("x")
        self.assertEqual(store.saves, 1)
        self.assertEqual(store.data["actions"], 2)

    def test_orchestrator_exposes_keeper_action_log_limit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            orchestrator = Orchestrator(
                bridge=InMemoryBridge(),
                ai=ScriptedAIClient([
                    {"decision": "continue", "reason": "idle"}
                ]),
                store=JsonStateStore(root / "state"),
                incidents=IncidentManager(root / "incidents"),
                keeper_policy=KeeperPolicy(action_log_limit=7),
            )
            self.assertEqual(orchestrator.keeper.action_log.maxlen, 7)


if __name__ == "__main__":
    unittest.main()
