import unittest
from gar_ai.blueprint_ir import BlueprintIR
from gar_ai.smelting import SmeltingPlanner,SmeltingPlanRequest
class T(unittest.TestCase):
 def test_all_variants(self):
  p=SmeltingPlanner()
  for n in (8,16,24,48):
   for rows in ('single-row','double-row'):
    ir=p.plan(SmeltingPlanRequest(f'b{n}{rows}','iron-plate',n,rows,'left','south'));self.assertEqual(sum(e.role=='furnace' for e in ir.entities),n);self.assertEqual(BlueprintIR.from_dict(ir.to_dict()).blueprint_id,ir.blueprint_id)
 def test_ports(self):
  ir=SmeltingPlanner().plan(SmeltingPlanRequest('b','copper-plate',8,'single-row','right','north'));self.assertEqual(ir.input_ports[0].direction,'east');self.assertEqual(ir.expansion_ports[0].direction,'north')
