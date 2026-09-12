import unittest

from gar_ai.budget import AtomicBudgetLimits, BudgetContext, BudgetExceeded, TaskBudgetLimits


class BudgetTests(unittest.TestCase):
    def test_atomic_and_task_budget_take_stricter_limit(self):
        ctx = BudgetContext(AtomicBudgetLimits(max_total_actions=10, per_tool={"place_verified": 2}), TaskBudgetLimits(max_actions=3, max_entities=2, max_material_cost=10, max_duration_sec=60))
        ctx.consume_atomic("place_verified", entities=1, material_cost=1)
        ctx.consume_atomic("place_verified", entities=1, material_cost=1)
        with self.assertRaises(BudgetExceeded):
            ctx.consume_atomic("place_verified")

    def test_budget_restores_across_restart(self):
        ctx = BudgetContext(AtomicBudgetLimits(max_total_actions=5), TaskBudgetLimits(max_actions=5, max_duration_sec=60))
        ctx.consume_atomic("move_to_verified")
        restored = BudgetContext(AtomicBudgetLimits(max_total_actions=5), TaskBudgetLimits(max_actions=5, max_duration_sec=60), restored=ctx.snapshot().to_dict())
        self.assertEqual(restored.actions, 1)
        self.assertEqual(restored.per_tool["move_to_verified"], 1)


if __name__ == "__main__": unittest.main()
