from __future__ import annotations
from dataclasses import asdict,dataclass,field
from enum import Enum
from pathlib import Path
from typing import Any
import json,os,time
class ProgressKind(str,Enum):TECHNOLOGY='technology_progress';INVENTORY='target_inventory_growth';PRODUCTION='production_rate_growth';ENTITY='verified_entity_added';POWER='area_powered';WORKITEM='workitem_closed'
@dataclass(slots=True)
class MetricsState:
    started_at_epoch:float=field(default_factory=time.time);meaningful_progress_events:int=0;recoveries_attempted:int=0;recoveries_succeeded:int=0;human_interventions:int=0;ai_calls:int=0;ai_cost:float=0.0;false_success_count:int=0;loop_count:int=0;major_tasks_attempted:int=0;major_tasks_recovered:int=0;keeper_runtime_sec:float=0.0;keeper_zero_token_sec:float=0.0;no_progress_total_sec:float=0.0;no_progress_events:int=0;rollback_count:int=0;batches_attempted:int=0;batches_completed:int=0;progress_by_kind:dict[str,int]=field(default_factory=dict)
    def to_dict(self):return asdict(self)
class MetricsRecorder:
    def __init__(self,path:str|Path|None=None,*,state:MetricsState|None=None,clock=time.time):self.path=Path(path) if path is not None else None;self.clock=clock;self.state=state or MetricsState(started_at_epoch=clock());self._load()
    def _load(self):
        if self.path is not None and self.path.exists():self.state=MetricsState(**json.loads(self.path.read_text(encoding='utf-8')))
    def _save(self):
        if self.path is None:return
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix(self.path.suffix+'.tmp');tmp.write_text(json.dumps(self.state.to_dict(),ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8');os.replace(tmp,self.path)
    def record_progress(self,kind:ProgressKind):self.state.meaningful_progress_events+=1;self.state.progress_by_kind[kind.value]=self.state.progress_by_kind.get(kind.value,0)+1;self._save()
    def record_ai_call(self,*,cost:float=0.0):self.state.ai_calls+=1;self.state.ai_cost+=float(cost);self._save()
    def record_keeper_runtime(self,seconds:float,*,used_ai_tokens:bool=False):
        seconds=max(0.0,float(seconds));self.state.keeper_runtime_sec+=seconds
        if not used_ai_tokens:self.state.keeper_zero_token_sec+=seconds
        self._save()
    def record_recovery(self,*,success:bool):self.state.recoveries_attempted+=1;self.state.recoveries_succeeded+=int(success);self._save()
    def record_intervention(self):self.state.human_interventions+=1;self._save()
    def record_false_success(self):self.state.false_success_count+=1;self._save()
    def record_loop(self):self.state.loop_count+=1;self._save()
    def record_no_progress(self,seconds:float):self.state.no_progress_events+=1;self.state.no_progress_total_sec+=max(0.0,float(seconds));self._save()
    def record_batch(self,*,completed:bool):self.state.batches_attempted+=1;self.state.batches_completed+=int(completed);self._save()
    def report(self):
        h=max((self.clock()-self.state.started_at_epoch)/3600.0,1e-9)
        return {'Progress Rate':self.state.meaningful_progress_events/h,'Recovery Rate':self.state.recoveries_succeeded/self.state.recoveries_attempted if self.state.recoveries_attempted else 1.0,'Human Intervention Rate':self.state.human_interventions/h,'AI Cost / Game Hour':self.state.ai_cost/h,'False Success Count':self.state.false_success_count,'Loop Count':self.state.loop_count,'Task Recovery Rate':self.state.major_tasks_recovered/self.state.major_tasks_attempted if self.state.major_tasks_attempted else 1.0,'Strategic AI Calls / Hour':self.state.ai_calls/h,'Keeper Zero-Token Ratio':self.state.keeper_zero_token_sec/self.state.keeper_runtime_sec if self.state.keeper_runtime_sec else 1.0,'Mean No-Progress Duration':self.state.no_progress_total_sec/self.state.no_progress_events if self.state.no_progress_events else 0.0,'Rollback Count':self.state.rollback_count,'Batch Completion Rate':self.state.batches_completed/self.state.batches_attempted if self.state.batches_attempted else 1.0}
