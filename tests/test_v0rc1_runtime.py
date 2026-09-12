import sys
import tempfile
import types
import unittest
from pathlib import Path

from gar_ai.batch_budget import (
    BatchBudgetContext,
    GlobalBudgetLimits,
)
from gar_ai.batch_executor import smelting_operational_predicate
from gar_ai.budget import (
    AtomicBudgetLimits,
    BudgetContext,
    BudgetExceeded,
    TaskBudgetLimits,
)
from gar_ai.cli import load_bridge_factory
from gar_ai.controller import ControllerConfig, ControllerLoop
from gar_ai.keeper import Keeper, KeeperPolicy
from gar_ai.mock_bridge import InMemoryBridge
from gar_ai.orchestrator import OrchestratorResult
from gar_ai.smelting import SmeltingPlanRequest, SmeltingPlanner
from gar_ai.storage import JsonStateStore
from gar_ai.watchdog import Watchdog


class _Store:
    def load_task(self):
        return None


class _SafeStopOrchestrator:
    def __init__(self):
        self.store = _Store()
        self.calls = []

    def tick(self, *, trigger="event"):
        self.calls.append(trigger)
        return OrchestratorResult("safe_stop", "ai_error")


class _StopAfterTwoWaits:
    def __init__(self):
        self.waits = 0

    def is_set(self):
        return self.waits >= 2

    def wait(self, timeout):
        self.waits += 1
        return self.is_set()


class V0RC1RuntimeTests(unittest.TestCase):
    def test_run_forever_enters_safe_hold_without_exiting_process_loop(self):
        orchestrator = _SafeStopOrchestrator()
        loop = ControllerLoop(
            orchestrator,
            ControllerConfig(heartbeat_sec=0, strategic_review_sec=999),
        )
        stop = _StopAfterTwoWaits()

        loop.run_forever(stop)

        self.assertTrue(loop.safe_hold)
        self.assertEqual(loop.safe_hold_reason, "ai_error")
        # The second heartbeat stayed inside SAFE_HOLD instead of calling AI again.
        self.assertEqual(orchestrator.calls, ["startup"])
        self.assertEqual(stop.waits, 2)

    def test_resume_forces_fresh_user_resume_tick(self):
        orchestrator = _SafeStopOrchestrator()
        loop = ControllerLoop(orchestrator)
        loop.enter_safe_hold("test")
        loop.resume()

        result = loop.step()

        self.assertEqual(result.status, "safe_stop")
        self.assertEqual(orchestrator.calls, ["user_resume"])

    def test_keeper_action_log_is_bounded_but_full_history_is_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            store = JsonStateStore(Path(td) / "state")
            keeper = Keeper(
                InMemoryBridge(),
                store,
                Watchdog(),
                KeeperPolicy(action_log_limit=2),
            )

            keeper._append_action({"n": 1})
            keeper._append_action({"n": 2})
            keeper._append_action({"n": 3})

            self.assertEqual(list(keeper.action_log), [{"n": 2}, {"n": 3}])
            lines = store.action_history_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)

    def test_global_budget_survives_new_batch_context(self):
        with tempfile.TemporaryDirectory() as td:
            store = JsonStateStore(Path(td) / "state")
            limits = GlobalBudgetLimits(
                max_actions=1,
                max_entities=10,
                max_material_cost=10,
                window_sec=3600,
            )

            parent1 = BudgetContext(
                AtomicBudgetLimits(10),
                TaskBudgetLimits(
                    max_actions=10,
                    max_entities=10,
                    max_material_cost=10,
                ),
                task_id="t1",
            )
            first = BatchBudgetContext(
                parent1,
                batch_id="b1",
                global_limits=limits,
                global_store=store,
            )
            first.consume_atomic("x")

            parent2 = BudgetContext(
                AtomicBudgetLimits(10),
                TaskBudgetLimits(
                    max_actions=10,
                    max_entities=10,
                    max_material_cost=10,
                ),
                task_id="t2",
            )
            second = BatchBudgetContext(
                parent2,
                batch_id="b2",
                global_limits=limits,
                global_store=store,
            )

            with self.assertRaises(BudgetExceeded) as cm:
                second.consume_atomic("x")
            self.assertEqual(cm.exception.code, "GLOBAL_BUDGET_EXCEEDED")

    def test_smelting_final_verification_requires_real_output_rate(self):
        ir = SmeltingPlanner().plan(
            SmeltingPlanRequest(
                "smelt",
                "iron-plate",
                8,
                "single-row",
                "left",
                "south",
            )
        )

        with self.assertRaises(ValueError):
            smelting_operational_predicate(ir, min_product_rate=0)

        predicate = smelting_operational_predicate(
            ir,
            min_product_rate=30,
            min_power_margin=0.2,
        )
        snapshot = {
            "entities": [
                {
                    "name": entity.name,
                    "position": [entity.x, entity.y],
                }
                for entity in ir.entities
            ],
            "power": {"margin": 0.3},
            "production": {"iron-plate": 0},
        }

        ok, evidence = predicate(snapshot)
        self.assertFalse(ok)
        self.assertEqual(evidence["min_product_rate"], 30)

    def test_cli_bridge_factory_loader_is_real_wiring_point(self):
        module_name = "_gar_ai_test_bridge_factory"
        module = types.ModuleType(module_name)
        module.create_bridge = InMemoryBridge
        sys.modules[module_name] = module
        try:
            bridge = load_bridge_factory(f"{module_name}:create_bridge")
            self.assertIsInstance(bridge, InMemoryBridge)
        finally:
            sys.modules.pop(module_name, None)


if __name__ == "__main__":
    unittest.main()
