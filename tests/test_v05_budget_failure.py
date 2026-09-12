import unittest
from gar_ai.budget import AtomicBudgetLimits,BudgetContext,BudgetExceeded,TaskBudgetLimits
from gar_ai.batch_budget import *
class T(unittest.TestCase):
 def test_layers(self):
  p=BudgetContext(AtomicBudgetLimits(10),TaskBudgetLimits(max_actions=10,max_entities=10,max_material_cost=20),task_id='t');b=BatchBudgetContext(p,batch_id='b',batch_limits=BatchBudgetLimits(max_actions=2,max_entities=2,max_material_cost=5),global_limits=GlobalBudgetLimits(10,10,20));b.consume_atomic('x',entities=1,material_cost=1);b.consume_atomic('x',entities=1,material_cost=1)
  with self.assertRaises(BudgetExceeded):b.consume_atomic('x')
 def test_global(self):
  p=BudgetContext(AtomicBudgetLimits(10),TaskBudgetLimits(max_actions=10,max_entities=10,max_material_cost=20),task_id='t');b=BatchBudgetContext(p,batch_id='b',global_limits=GlobalBudgetLimits(1,10,20));b.consume_atomic('x')
  with self.assertRaises(BudgetExceeded) as cm:b.consume_atomic('x')
  self.assertEqual(cm.exception.code,'GLOBAL_BUDGET_EXCEEDED')
