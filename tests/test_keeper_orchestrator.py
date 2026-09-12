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


class KeeperOrchestratorTests(unittest.TestCase):
    def test_research_starvation_closed_loop(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = InMemoryBridge()
            bridge.state["entities"].append({"name": "lab", "position": [5.0, 5.0], "inventory": {}, "recipe": None})
            bridge.state["research"].update({"technology": "automation", "progress": 0.20, "unit_count": 10, "science_supply": {}, "state": "starved"})
            ai = ScriptedAIClient([{"decision": "create_task", "reason": "research is starved", "plan_patch": {"mid_term": "restore research", "current": "supply science packs", "next": "continue automation", "watch": ["research.state", "research.progress"]}, "task": {"task_id": "restore-research-001", "objective": "restore research progress", "reason": "current research is starved", "desired_state": {"research.state": "progressing"}, "operations": [{"tool": "ensure_item_verified", "args": {"item": "automation-science-pack", "count": 3}}, {"tool": "transfer_verified", "args": {"item": "automation-science-pack", "x": 5, "y": 5, "target_count": 3}}], "success_when": [{"path": "research.state", "op": "eq", "value": "progressing"}], "abort_if": []}}])
            store = JsonStateStore(Path(td) / "state")
            orch = Orchestrator(bridge=bridge, ai=ai, store=store, incidents=IncidentManager(Path(td) / "incidents"), watchdog=Watchdog(WatchdogConfig(no_progress_sec=999)))
            result = orch.tick(trigger="startup")
            self.assertEqual(result.status, "task_completed")
            self.assertEqual(ai.calls, 1)
            state = bridge.snapshot()
            self.assertEqual(state["research"]["state"], "progressing")
            self.assertGreater(state["research"]["progress"], 0.20)
            self.assertIsNone(store.load_task())

    def test_restart_resumes_from_verified_cursor_without_repeating_previous_step(self):
        with tempfile.TemporaryDirectory() as td:
            bridge = InMemoryBridge()
            bridge.reject_actions.add("place_entity")
            store = JsonStateStore(Path(td) / "state")
            watchdog = Watchdog(WatchdogConfig(no_progress_sec=999))
            task = TaskSpec.from_dict({"task_id": "resume-001", "objective": "prepare lab", "reason": "test restart", "desired_state": {"lab": "present"}, "operations": [{"tool": "ensure_item_verified", "args": {"item": "lab", "count": 1}}, {"tool": "place_verified", "args": {"name": "lab", "x": 2, "y": 3}}], "success_when": [], "abort_if": []})
            first = Keeper(bridge, store, watchdog).execute(task)
            self.assertEqual(first.status, "blocked")
            loaded = store.load_task()
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.cursor, 1)
            self.assertEqual(bridge.snapshot()["player"]["inventory"]["lab"], 1)
            bridge.reject_actions.clear()
            second = Keeper(bridge, store, watchdog).execute(loaded)
            self.assertEqual(second.status, "completed")
            self.assertEqual(bridge.snapshot()["player"]["inventory"]["lab"], 1)
            labs = [e for e in bridge.snapshot()["entities"] if e["name"] == "lab"]
            self.assertEqual(len(labs), 1)
            self.assertGreaterEqual(store.load_runtime()["actions"], 3)


if __name__ == "__main__": unittest.main()
