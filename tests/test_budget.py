import unittest

from gar_ai.budget import AtomicBudgetLimits, BudgetContext, BudgetExceeded, TaskBudgetLimits


class BudgetTests(unittest.TestCase):
    def test_atomic_and_task_are_independent_limits(self):
        ctx = BudgetContext(AtomicBudgetLimits(max_total_actions=10, per_tool={"place_verified": 2}), TaskBudgetLimits(max_actions=3, max_entities=2, max_material_cost=10, max_duration_sec=60), task_id="t1")
        ctx.consume_atomic("place_verified", entities=1, material_cost=1); ctx.consume_atomic("place_verified", entities=1, material_cost=1)
        with self.assertRaises(BudgetExceeded) as cm: ctx.consume_atomic("place_verified")
        self.assertEqual(cm.exception.code, "ATOMIC_BUDGET_EXCEEDED")

    def test_budget_restores_only_for_same_task(self):
        ctx = BudgetContext(AtomicBudgetLimits(max_total_actions=5), TaskBudgetLimits(max_actions=5, max_duration_sec=60), task_id="t1"); ctx.consume_atomic("move_to_verified"); snap = ctx.snapshot().to_dict()
        same = BudgetContext(AtomicBudgetLimits(max_total_actions=5), TaskBudgetLimits(max_actions=5, max_duration_sec=60), task_id="t1", restored=snap)
        other = BudgetContext(AtomicBudgetLimits(max_total_actions=5), TaskBudgetLimits(max_actions=5, max_duration_sec=60), task_id="t2", restored=snap)
        self.assertEqual(same.actions, 1); self.assertEqual(other.actions, 0)

    def test_replan_budget_is_structured(self):
        ctx = BudgetContext(task=TaskBudgetLimits(max_replans=1), task_id="t"); ctx.record_replan()
        with self.assertRaises(BudgetExceeded) as cm: ctx.record_replan()
        self.assertEqual(cm.exception.code, "REPLAN_BUDGET_EXCEEDED")


if __name__ == "__main__": unittest.main()
