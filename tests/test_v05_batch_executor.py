import tempfile,unittest
from dataclasses import dataclass
from pathlib import Path
from gar_ai.batch_budget import BatchBudgetContext,BatchBudgetLimits
from gar_ai.batch_executor import BatchExecutor,smelting_operational_predicate
from gar_ai.budget import AtomicBudgetLimits,BudgetContext,TaskBudgetLimits
from gar_ai.coordination import AreaLockManager,MaterialReservationManager
from gar_ai.journal import OperationJournal
from gar_ai.metrics import MetricsRecorder
from gar_ai.smelting import SmeltingPlanner,SmeltingPlanRequest
from gar_ai.async_verify import AsyncVerificationSpec
@dataclass
class R:ok:bool;changed:bool;reason:str|None=None;error_code:str|None=None
class Surface:
 def __init__(self,state,budget):self.state=state;self.budget=budget
 def call(self,tool,args):
  self.budget.consume_atomic(tool,entities=1,material_cost=1);pos=[float(args['x']),float(args['y'])];name=args['name']
  for e in self.state['entities']:
   if e['name']==name and e['position']==pos:return R(True,False)
  self.state['entities'].append({'name':name,'position':pos});return R(True,True)
class T(unittest.TestCase):
 def make(self,td,limit=500):
  ir=SmeltingPlanner().plan(SmeltingPlanRequest('smelt','iron-plate',8,'single-row','left','south'));state={'player':{'inventory':dict(ir.required_items)},'entities':[],'power':{'margin':.3},'production':{'iron-plate':0}};parent=BudgetContext(AtomicBudgetLimits(1000),TaskBudgetLimits(max_actions=1000,max_entities=1000,max_material_cost=10000,max_duration_sec=999),task_id='t');bb=BatchBudgetContext(parent,batch_id='b',batch_limits=BatchBudgetLimits(max_actions=limit,max_entities=1000,max_material_cost=10000,max_duration_sec=999,checkpoint_every_entities=5));surf=Surface(state,bb);exe=BatchExecutor(surface=surf,batch_budget=bb,area_locks=AreaLockManager(Path(td)/'l.json'),reservations=MaterialReservationManager(Path(td)/'r.json'),journal=OperationJournal(Path(td)/'ops.jsonl'),snapshot=lambda:state,metrics=MetricsRecorder(Path(td)/'metrics.json'));return ir,state,exe
 def test_complete(self):
  with tempfile.TemporaryDirectory() as td:
   ir,state,e=self.make(td);r=e.execute_placements(task_id='t',batch_id='b',ir=ir,checkpoint=lambda s,n,total:True);self.assertEqual(r.status,'constructed');state['production']['iron-plate']=60;p=e.begin_final_verification(spec=AsyncVerificationSpec('final',10,0,1));f=e.poll_final_verification(task_id='t',batch_id='b',pending=p,predicate=smelting_operational_predicate(ir,min_power_margin=.2,min_product_rate=30));self.assertEqual(f.status,'completed');self.assertEqual(len(e.area_locks.locks()),0)
 def test_budget_partial(self):
  with tempfile.TemporaryDirectory() as td:
   ir,state,e=self.make(td,3);r=e.execute_placements(task_id='t',batch_id='b',ir=ir);self.assertEqual(r.status,'partial');self.assertEqual(r.error_code,'BATCH_BUDGET_EXCEEDED');self.assertEqual(len(e.area_locks.locks()),0);self.assertGreater(len(state['entities']),0);self.assertLess(len(state['entities']),len(ir.entities));self.assertEqual(e.reservations.get('materials:b').status,'released')
