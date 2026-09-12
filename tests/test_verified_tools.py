import unittest

from gar_ai.budget import AtomicBudgetLimits, BudgetContext, TaskBudgetLimits
from gar_ai.mock_bridge import InMemoryBridge
from gar_ai.types import Ack, ToolOutcome
from gar_ai.verified_tools import VerifiedToolSurface


class VerifiedToolSurfaceTests(unittest.TestCase):
    def make_surface(self, bridge):
        budget = BudgetContext(AtomicBudgetLimits(max_total_actions=30), TaskBudgetLimits(max_actions=30, max_entities=5, max_material_cost=50, max_duration_sec=60), task_id="test")
        return VerifiedToolSurface(bridge, budget), budget

    def test_ack_plus_fresh_state_required(self):
        bridge = InMemoryBridge(); bridge.accept_without_effect.add("place_entity"); surface, _ = self.make_surface(bridge)
        result = surface.place_verified("stone-furnace", 3, 4); self.assertEqual(result.outcome, ToolOutcome.UNVERIFIED); self.assertFalse(result.ok)
    def test_rejected_ack_is_blocked(self):
        bridge = InMemoryBridge(); bridge.reject_actions.add("move_to"); surface, _ = self.make_surface(bridge); self.assertEqual(surface.move_to_verified(10, 10).outcome, ToolOutcome.BLOCKED)
    def test_place_is_idempotent_and_noop_does_not_spend_budget(self):
        bridge = InMemoryBridge(); surface, budget = self.make_surface(bridge); self.assertEqual(surface.place_verified("lab", 1, 2).outcome, ToolOutcome.VERIFIED); self.assertEqual(surface.place_verified("lab", 1, 2).outcome, ToolOutcome.NOOP); self.assertEqual(budget.actions, 1)
    def test_place_uses_coordinate_tolerance(self):
        bridge = InMemoryBridge(); bridge.round_positions_to = 0; surface, _ = self.make_surface(bridge); self.assertTrue(surface.place_verified("lab", 1.05, 2.04, tolerance=0.10).ok)
    def test_transfer_target_count_is_idempotent(self):
        bridge = InMemoryBridge(); bridge.state["entities"].append({"name": "lab", "position": [1.0, 2.0], "inventory": {}, "recipe": None}); bridge.state["player"]["inventory"]["automation-science-pack"] = 5; surface, budget = self.make_surface(bridge); self.assertTrue(surface.transfer_verified("automation-science-pack", 1, 2, target_count=3).ok); self.assertEqual(surface.transfer_verified("automation-science-pack", 1, 2, target_count=3).outcome, ToolOutcome.NOOP); self.assertEqual(budget.actions, 1)
    def test_research_verified_does_not_accept_starved_selection(self):
        bridge = InMemoryBridge(); bridge.state["research"].update({"technology": None, "progress": 0.0, "science_supply": {}, "state": "idle"}); surface, _ = self.make_surface(bridge); result = surface.research_verified("automation"); self.assertEqual(result.outcome, ToolOutcome.UNVERIFIED); self.assertEqual(bridge.snapshot()["research"]["state"], "starved")
    def test_research_verified_accepts_progressing_state(self):
        bridge = InMemoryBridge(); bridge.state["research"].update({"technology": None, "progress": 0.0, "science_supply": {"automation-science-pack": 2}, "state": "idle"}); surface, _ = self.make_surface(bridge); self.assertTrue(surface.research_verified("automation").ok)
    def test_set_recipe_verified(self):
        bridge = InMemoryBridge(); bridge.state["entities"].append({"name": "assembling-machine-1", "position": [1.0, 2.0], "inventory": {}, "recipe": None}); surface, _ = self.make_surface(bridge); result = surface.set_recipe_verified(1, 2, "iron-gear-wheel"); self.assertTrue(result.ok); self.assertEqual(bridge.snapshot()["entities"][0]["recipe"], "iron-gear-wheel")
    def test_query_technology_and_get_digest(self):
        bridge = InMemoryBridge(); bridge.technologies["automation"] = {"researched": False}; surface, _ = self.make_surface(bridge); self.assertEqual(surface.query_technology("automation").evidence["technology"]["researched"], False); digest = surface.get_digest().evidence["digest"]; self.assertIn("schema_version", digest); self.assertIn("research", digest)
    def test_ack_is_case_insensitive(self): self.assertTrue(Ack("Accepted").accepted)


if __name__ == "__main__": unittest.main()
