from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
import time
from .contracts import DIGEST_SCHEMA_VERSION
from .types import MasterPlan
def _resource_view(snapshot:Mapping[str,Any],name:str):
    raw=(snapshot.get('resources') or {}).get(name)
    if isinstance(raw,Mapping):return {'stock':raw.get('stock'),'rate':raw.get('rate')}
    return {'stock':None if raw is None else raw,'rate':None}
class StateDigestBuilder:
    SCHEMA_VERSION=DIGEST_SCHEMA_VERSION
    def build(self,snapshot:Mapping[str,Any],*,goal:str|None,agent_state:Mapping[str,Any]|None=None,recent_failure:Mapping[str,Any]|None=None,plan:MasterPlan|None=None):
        a=agent_state or {};r=snapshot.get('research') if isinstance(snapshot.get('research'),Mapping) else {};p=snapshot.get('power') if isinstance(snapshot.get('power'),Mapping) else {};t=snapshot.get('threat') if isinstance(snapshot.get('threat'),Mapping) else {};f=recent_failure or {};plan=plan or MasterPlan();b=snapshot.get('bottleneck')
        if b is None and r.get('state')=='starved':b='research_starved'
        now=time.time();iso=datetime.fromtimestamp(now,tz=timezone.utc).isoformat()
        return {'schema_version':self.SCHEMA_VERSION,'generated_at':iso,'generated_at_epoch':now,'game_tick':snapshot.get('game_tick'),'goal':goal,'agent':{'task_id':a.get('task_id'),'task_status':a.get('task_status','idle'),'task_progress':a.get('task_progress',0.0),'meaningful_progress_age_sec':a.get('meaningful_progress_age_sec'),'mode':a.get('mode','normal')},'power':{'margin':p.get('margin'),'status':p.get('status')},'resources':{'iron':_resource_view(snapshot,'iron'),'copper':_resource_view(snapshot,'copper'),'coal':_resource_view(snapshot,'coal')},'research':{'technology':r.get('technology'),'progress':r.get('progress'),'unit_count':r.get('unit_count'),'science_supply':r.get('science_supply'),'state':r.get('state')},'bottleneck':b,'recent_failure':{'task_id':f.get('task_id'),'reason':f.get('reason'),'attempts':int(f.get('attempts',0) or 0),'evidence':f.get('evidence')},'threat':{'level':t.get('level')},'plan':{'current':plan.current,'next':plan.next,'watch':list(plan.watch)},'_evidence':{'game_tick':snapshot.get('game_tick'),'observed_at_epoch':now,'observed_at':iso}}
