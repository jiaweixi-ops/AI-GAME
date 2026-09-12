import unittest

from gar_ai.budget import AtomicBudgetLimits, BudgetContext, TaskBudgetLimits
from gar_ai.mock_bridge import InMemoryBridge
from gar_ai.types import ToolOutcome
from gar_ai.verified_tools import VerifiedToolSurface


class VerifiedToolSurfaceTests(unittest.TestCase):
    def make_surface(self, bridge):
        budget = BudgetContext(AtomicBudgetLimits(max_total_actions=20), TaskBudgetLimits(max_actions=20, max_entities=5, max_material_cost=50, max_duration_sec=60))
        return VerifiedToolSurface(bridge, budget), budget

    def test_ack_plus_fresh_state_required(self):
        bridge = InMemoryBridge()
        bridge.accept_without_effect.add("place_entity")
        surface, _ = self.make_surface(bridge)
        result = surface.place_verified("stone-furnace", 3, 4)
        self.assertEqual(result.outcome, ToolOutcome.UNVERIFIED)
        self.assertFalse(result.ok)

    def test_rejected_ack_is_blocked(self):
        bridge = InMemoryBridge()
        bridge.reject_actions.add("move_to")
        surface, _ = self.make_surface(bridge)
        result = surface.move_to_verified(10, 10)
        self.assertEqual(result.outcome, ToolOutcome.BLOCKED)

    def test_place_is_idempotent(self):
        bridge = InMemoryBridge()
        surface, budget = self.make_surface(bridge)
        first = surface.place_verified("lab", 1, 2)
        second = surface.place_verified("lab", 1, 2)
        self.assertEqual(first.outcome, ToolOutcome.VERIFIED)
        self.assertEqual(second.outcome, ToolOutcome.NOOP)
        self.assertEqual(len(bridge.snapshot()["entities"]), 1)
        self.assertEqual(budget.actions, 1)

    def test_transfer_uses_target_count_and_is_idempotent(self):
        bridge = InMemoryBridge()
        bridge.state["entities"].append({"name": "lab", "position": [1.0, 2.0], "inventory": {}, "recipe": None})
        bridge.state["player"]["inventory"]["automation-science-pack"] = 5
        surface, budget = self.make_surface(bridge)
        first = surface.transfer_verified("automation-science-pack", 1, 2, target_count=3)
        second = surface.transfer_verified("automation-science-pack", 1, 2, target_count=3)
        self.assertTrue(first.ok)
        self.assertEqual(second.outcome, ToolOutcome.NOOP)
        lab = bridge.snapshot()["entities"][0]
        self.assertEqual(lab["inventory"]["automation-science-pack"], 3)
        self.assertEqual(budget.actions, 1)


if __name__ == "__main__": unittest.main()
