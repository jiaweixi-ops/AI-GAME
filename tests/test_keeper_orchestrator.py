import tempfile
import unittest
from pathlib import Path

from gar_ai.ai_client import ScriptedAIClient
from gar_ai.incidents import IncidentManager
from gar_ai.keeper import Keeper
from gar_ai.mock_bridge import InMemoryBridge
from gar_ai.orchestrator import Orchestrator
from gar_ai.storage import JsonStateStore
from gar_ai.types import TaskSpec
from gar_ai.watchdog import Watchdog, WatchdogConfig


def research_task(task_id="restore-research-001"):
    return {"task_id": task_id, "objective": "restore research progress", "reason": "research is starved", "desired_state": {"research.state": "progressing"}, "operations": [{"tool": "ensure_item_verified", "args": {"item": "automation-science-pack", "count": 3}}, {"tool": "transfer_verified", "args": {"item": "automation-science-pack", "x": 5, "y": 5, "target_count": 3}}], "success_when": [{"path": "research.state", "op": "eq", "value": "progressing"}], "abort_if": []}


class KeeperOrchestratorTests(unittest.TestCase):
    def make_bridge(self):
        bridge = InMemoryBridge(); bridge.state["entities"].append({"name": "lab", "position": [5.0, 5.0], "inventory": {}, "recipe": None}); bridge.state["research"].update({"technology": "automation", "progress": 0.20, "unit_count": 10, "science_supply": {}, "state": "starved"}); return bridge

    def test_research_starvation_closed_loop(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = self.make_bridge(); ai = ScriptedAIClient([{"decision": "create_task", "reason": "research is starved", "plan_patch": {"current": "supply science packs", "next": "continue automation"}, "task": research_task()}]); store = JsonStateStore(Path(td) / "state"); orch = Orchestrator(bridge=bridge, ai=ai, store=store, incidents=IncidentManager(Path(td) / "incidents"), watchdog=Watchdog(WatchdogConfig(no_progress_sec=999))); result = orch.tick(trigger="startup"); self.assertEqual(result.status, "task_completed"); self.assertEqual(bridge.snapshot()["research"]["state"], "progressing"); self.assertGreater(bridge.snapshot()["research"]["progress"], 0.20)

    def test_blocked_task_immediately_replans(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = self.make_bridge(); bridge.reject_actions.add("ensure_item")
            first = {"decision": "create_task", "task": research_task("bad")}
            second = {"decision": "create_task", "task": {"task_id": "replan-good", "objective": "move safely", "reason": "fallback", "desired_state": {"player.position": [1.0, 1.0]}, "operations": [{"tool": "move_to_verified", "args": {"x": 1, "y": 1}}], "success_when": [{"path": "player.position", "op": "eq", "value": [1.0, 1.0]}], "abort_if": []}}
            ai = ScriptedAIClient([first, second]); store = JsonStateStore(Path(td) / "state"); orch = Orchestrator(bridge=bridge, ai=ai, store=store, incidents=IncidentManager(Path(td) / "incidents"), watchdog=Watchdog(WatchdogConfig(no_progress_sec=999))); result = orch.tick(trigger="startup"); self.assertEqual(result.status, "task_completed"); self.assertEqual(ai.calls, 2); self.assertEqual(store.load_metrics()["replans"], 1)

    def test_ai_error_falls_back_to_safe_stop_and_incident(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = self.make_bridge(); ai = ScriptedAIClient([RuntimeError("timeout")]); store = JsonStateStore(Path(td) / "state"); incident_root = Path(td) / "incidents"; orch = Orchestrator(bridge=bridge, ai=ai, store=store, incidents=IncidentManager(incident_root), watchdog=Watchdog(WatchdogConfig(no_progress_sec=999))); result = orch.tick(trigger="startup"); self.assertEqual(result.status, "safe_stop"); self.assertTrue(any(incident_root.iterdir()))

    def test_keeper_reconciles_from_live_state_not_cursor_only(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = InMemoryBridge(); store = JsonStateStore(Path(td) / "state"); task = TaskSpec.from_dict({"task_id": "reconcile", "objective": "have lab", "reason": "test", "desired_state": {"player.inventory.lab": 1}, "operations": [{"tool": "ensure_item_verified", "args": {"item": "lab", "count": 1}}], "success_when": [{"path": "player.inventory.lab", "op": "gte", "value": 1}], "abort_if": [], "cursor": 1, "status": "running"}); result = Keeper(bridge, store, Watchdog(WatchdogConfig(no_progress_sec=999))).execute(task); self.assertEqual(result.status, "completed"); self.assertEqual(bridge.snapshot()["player"]["inventory"]["lab"], 1)

    def test_empty_success_conditions_block(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = InMemoryBridge(); store = JsonStateStore(Path(td) / "state"); task = TaskSpec.from_dict({"task_id": "bad", "objective": "bad", "reason": "bad", "desired_state": {}, "operations": [{"tool": "get_digest", "args": {}}], "success_when": [], "abort_if": []}); result = Keeper(bridge, store, Watchdog()).execute(task); self.assertEqual(result.error_code, "INVALID_TASK")

    def test_unknown_abort_path_fails_safe(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = InMemoryBridge(); store = JsonStateStore(Path(td) / "state"); task = TaskSpec.from_dict({"task_id": "bad-abort", "objective": "x", "reason": "x", "desired_state": {"player.position": [1.0, 1.0]}, "operations": [{"tool": "move_to_verified", "args": {"x": 1, "y": 1}}], "success_when": [{"path": "player.position", "op": "eq", "value": [1.0, 1.0]}], "abort_if": [{"path": "does.not.exist", "op": "truthy", "value": None}]}); result = Keeper(bridge, store, Watchdog()).execute(task); self.assertEqual(result.error_code, "ABORT_CONDITION_UNKNOWN")


if __name__ == "__main__": unittest.main()
