import unittest

from gar_ai.digest import StateDigestBuilder
from gar_ai.mock_bridge import InMemoryBridge
from gar_ai.types import MasterPlan


class DigestTests(unittest.TestCase):
    def test_fixed_v0_schema_and_starved_bottleneck(self):
        bridge = InMemoryBridge()
        bridge.state["research"].update({"technology": "automation", "progress": 0.2, "unit_count": 10, "state": "starved"})
        digest = StateDigestBuilder().build(bridge.snapshot(), goal="advance", agent_state={"task_status": "idle"}, recent_failure=None, plan=MasterPlan(current="restore research", next="continue tech", watch=["science"]))
        self.assertEqual(digest["schema_version"], "v0")
        for key in ("game_tick", "agent", "power", "resources", "research", "recent_failure", "threat"):
            self.assertIn(key, digest)
        self.assertEqual(digest["bottleneck"], "research_starved")
        self.assertEqual(digest["research"]["unit_count"], 10)


if __name__ == "__main__": unittest.main()
