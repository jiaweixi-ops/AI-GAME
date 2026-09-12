import tempfile
import unittest
from pathlib import Path

from gar_ai.ai_client import ScriptedAIClient
from gar_ai.controller import ControllerLoop
from gar_ai.incidents import IncidentManager
from gar_ai.mock_bridge import InMemoryBridge
from gar_ai.orchestrator import Orchestrator
from gar_ai.storage import JsonStateStore


class ControllerTests(unittest.TestCase):
    def test_controller_has_startup_driver(self):
        with tempfile.TemporaryDirectory() as td:
            ai = ScriptedAIClient([{"decision": "continue", "reason": "nothing to do"}]); store = JsonStateStore(Path(td) / "state")
            orch = Orchestrator(bridge=InMemoryBridge(), ai=ai, store=store, incidents=IncidentManager(Path(td) / "incidents")); loop = ControllerLoop(orch)
            result = loop.step(); self.assertEqual(result.trigger, "startup"); self.assertEqual(ai.calls, 1)


if __name__ == "__main__": unittest.main()
