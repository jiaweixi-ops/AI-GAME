import unittest
from gar_ai.digest import StateDigestBuilder
from gar_ai.mock_bridge import InMemoryBridge


class DigestTests(unittest.TestCase):
    def test_fixed_schema_contains_freshness_and_agent(self):
        d = StateDigestBuilder().build(InMemoryBridge().snapshot(), goal="x")
        for key in ["schema_version", "generated_at", "game_tick", "agent", "research", "recent_failure", "plan"]: self.assertIn(key, d)


if __name__ == "__main__": unittest.main()
