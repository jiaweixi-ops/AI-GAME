import unittest
from gar_ai.replan_guard import ReplanGuard,ReplanPolicy
from gar_ai.site_planner import SitePlanner
from gar_ai.coordination import Footprint
from gar_ai.types import Decision,TaskSpec,ToolOutcome,ToolResult
class C:
 def __init__(self):self.t=0
 def __call__(self):return self.t
class T(unittest.TestCase):
 def test_replan_limit(self):
  c=C();g=ReplanGuard(policy=ReplanPolicy(10,60,2),clock=c);g.record();self.assertFalse(g.allowed()[0]);c.t=11;g.record();c.t=22;self.assertFalse(g.allowed()[0]);c.t=70;self.assertTrue(g.allowed()[0])
 def test_site(self):
  p=SitePlanner();snap={'entities':[{'type':'tree','natural':True,'position':[1,1]},{'name':'asm','position':[20,20]}]};a=p.score(Footprint(0,0,5,5),snap,origin_x=0,origin_y=0);b=p.score(Footprint(18,18,22,22),snap,origin_x=20,origin_y=20);self.assertEqual(p.choose([a,b]),a)
 def test_versions_and_stamp(self):
  t=TaskSpec.from_dict({'task_id':'t','objective':'o','reason':'r','desired_state':{},'operations':[],'success_when':[],'abort_if':[]});self.assertEqual(t.task_schema_version,'1.1')
  with self.assertRaises(ValueError):Decision.from_dict({'decision':'continue','unknown':'x'})
  r=ToolResult('x',ToolOutcome.VERIFIED,False,False,after={'game_tick':42});self.assertEqual(r.evidence['_evidence']['game_tick'],42)
