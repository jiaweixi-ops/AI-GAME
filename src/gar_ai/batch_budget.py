from __future__ import annotations
from dataclasses import asdict,dataclass,field
import time
from typing import Any
from .budget import BudgetContext,BudgetExceeded
@dataclass(slots=True)
class GlobalBudgetLimits:max_actions:int=10000;max_entities:int=5000;max_material_cost:int=100000
@dataclass(slots=True)
class BatchBudgetLimits:max_actions:int=500;max_entities:int=256;max_material_cost:int=5000;max_duration_sec:float=900.0;max_failures:int=10;checkpoint_every_entities:int=10
@dataclass(slots=True)
class GlobalBudgetState:actions:int=0;entities:int=0;material_cost:int=0
@dataclass(slots=True)
class BatchBudgetState:
    batch_id:str;actions:int=0;entities:int=0;material_cost:int=0;failures:int=0;started_at_epoch:float=field(default_factory=time.time)
    def to_dict(self)->dict[str,Any]:return asdict(self)
class BatchBudgetContext:
    def __init__(self,parent:BudgetContext,*,batch_id:str,batch_limits:BatchBudgetLimits|None=None,global_limits:GlobalBudgetLimits|None=None,batch_state:BatchBudgetState|None=None,global_state:GlobalBudgetState|None=None,clock=time.time)->None:
        self.parent=parent;self.batch_limits=batch_limits or BatchBudgetLimits();self.global_limits=global_limits or GlobalBudgetLimits();self.batch=batch_state or BatchBudgetState(batch_id=batch_id,started_at_epoch=float(clock()));self.global_state=global_state or GlobalBudgetState();self.clock=clock
        if self.batch.batch_id!=batch_id:raise ValueError('batch_state.batch_id mismatch')
    def _preflight(self,*,entities:int,material_cost:int)->None:
        if self.clock()-self.batch.started_at_epoch>self.batch_limits.max_duration_sec:raise BudgetExceeded('BATCH_BUDGET_EXCEEDED','batch duration budget exceeded')
        if self.batch.actions+1>self.batch_limits.max_actions:raise BudgetExceeded('BATCH_BUDGET_EXCEEDED','batch action budget exceeded')
        if self.batch.entities+entities>self.batch_limits.max_entities:raise BudgetExceeded('BATCH_BUDGET_EXCEEDED','batch entity budget exceeded')
        if self.batch.material_cost+material_cost>self.batch_limits.max_material_cost:raise BudgetExceeded('BATCH_BUDGET_EXCEEDED','batch material budget exceeded')
        if self.global_state.actions+1>self.global_limits.max_actions:raise BudgetExceeded('GLOBAL_BUDGET_EXCEEDED','global action budget exceeded')
        if self.global_state.entities+entities>self.global_limits.max_entities:raise BudgetExceeded('GLOBAL_BUDGET_EXCEEDED','global entity budget exceeded')
        if self.global_state.material_cost+material_cost>self.global_limits.max_material_cost:raise BudgetExceeded('GLOBAL_BUDGET_EXCEEDED','global material budget exceeded')
    def consume_atomic(self,tool:str,*,entities:int=0,material_cost:int=0)->None:
        self._preflight(entities=entities,material_cost=material_cost);self.parent.consume_atomic(tool,entities=entities,material_cost=material_cost);self.batch.actions+=1;self.batch.entities+=entities;self.batch.material_cost+=material_cost;self.global_state.actions+=1;self.global_state.entities+=entities;self.global_state.material_cost+=material_cost
    def record_failure(self)->None:
        self.batch.failures+=1;self.parent.record_failure()
        if self.batch.failures>self.batch_limits.max_failures:raise BudgetExceeded('BATCH_BUDGET_EXCEEDED','batch failure budget exceeded')
    def checkpoint_due(self)->bool:
        n=self.batch_limits.checkpoint_every_entities;return n>0 and self.batch.entities>0 and self.batch.entities%n==0
