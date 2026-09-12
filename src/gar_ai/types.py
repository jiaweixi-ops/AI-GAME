from __future__ import annotations
from dataclasses import asdict,dataclass,field
from datetime import datetime,timezone
from enum import Enum
from typing import Any,Mapping
import time
from .contracts import TASK_SCHEMA_VERSION,TOOL_SCHEMA_VERSION,PROMPT_VERSION,require_compatible
def _reject_unknown(data:Mapping[str,Any],allowed:set[str],*,where:str):
    unknown=set(data)-allowed
    if unknown:raise ValueError(f"unknown fields in {where}: {sorted(unknown)}")
class ToolOutcome(str,Enum):VERIFIED='verified';UNVERIFIED='unverified';BLOCKED='blocked';NOOP='noop';PENDING='pending';TIMEOUT='timeout';FAILED='failed';REJECTED_FOR_STRATEGY_REVIEW='rejected_for_strategy_review'
@dataclass(slots=True)
class Ack:
    status:str;action_id:str|None=None;detail:str|None=None
    @property
    def accepted(self):return self.status.strip().lower()=='accepted'
@dataclass(slots=True)
class ToolResult:
    tool:str;outcome:ToolOutcome;changed:bool;meaningful_progress:bool;reason:str|None=None;error_code:str|None=None;before:Mapping[str,Any]|None=None;after:Mapping[str,Any]|None=None;evidence:Mapping[str,Any]=field(default_factory=dict);tool_schema_version:str=TOOL_SCHEMA_VERSION;game_tick:int|None=None;observed_at_epoch:float=field(default_factory=time.time);observed_at:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
    def __post_init__(self):
        source=self.after if isinstance(self.after,Mapping) else self.before if isinstance(self.before,Mapping) else None
        if self.game_tick is None and source is not None:
            try:self.game_tick=int(source.get('game_tick')) if source.get('game_tick') is not None else None
            except (TypeError,ValueError):self.game_tick=None
        ev=dict(self.evidence or {});ev.setdefault('_evidence',{'game_tick':self.game_tick,'observed_at_epoch':self.observed_at_epoch,'observed_at':self.observed_at});self.evidence=ev
    @property
    def ok(self):return self.outcome in {ToolOutcome.VERIFIED,ToolOutcome.NOOP}
    @property
    def terminal(self):return self.outcome!=ToolOutcome.PENDING
    def to_dict(self):d=asdict(self);d['outcome']=self.outcome.value;return d
@dataclass(slots=True)
class ToolCall:
    tool:str;args:dict[str,Any]=field(default_factory=dict);tool_schema_version:str=TOOL_SCHEMA_VERSION
    @classmethod
    def from_dict(cls,data):
        _reject_unknown(data,{'tool','args','tool_schema_version'},where='ToolCall');v=str(data.get('tool_schema_version',TOOL_SCHEMA_VERSION));require_compatible(v,TOOL_SCHEMA_VERSION,name='tool schema');tool=data.get('tool');args=data.get('args',{})
        if not isinstance(tool,str) or not tool:raise ValueError("tool call requires non-empty 'tool'")
        if not isinstance(args,dict):raise ValueError("tool call 'args' must be an object")
        return cls(tool,dict(args),v)
@dataclass(slots=True)
class Condition:
    path:str;op:str;value:Any=None
    @classmethod
    def from_dict(cls,data):
        _reject_unknown(data,{'path','op','value'},where='Condition');path=data.get('path');op=data.get('op');allowed={'eq','ne','gt','gte','lt','lte','contains','truthy','falsy','changed','increased','delta_gt'}
        if not isinstance(path,str) or not path:raise ValueError('condition.path must be a non-empty string')
        if op not in allowed:raise ValueError(f'unsupported condition op: {op!r}')
        return cls(path,str(op),data.get('value'))
@dataclass(slots=True)
class TaskSpec:
    task_id:str;objective:str;reason:str;desired_state:dict[str,Any];operations:list[ToolCall];success_when:list[Condition];abort_if:list[Condition];current_state:dict[str,Any]=field(default_factory=dict);remaining:dict[str,Any]=field(default_factory=dict);status:str='pending';cursor:int=0;failures:int=0;replans:int=0;task_schema_version:str=TASK_SCHEMA_VERSION
    @classmethod
    def from_dict(cls,data):
        _reject_unknown(data,{'task_id','objective','reason','desired_state','operations','success_when','abort_if','current_state','remaining','status','cursor','failures','replans','task_schema_version'},where='TaskSpec');v=str(data.get('task_schema_version',TASK_SCHEMA_VERSION));require_compatible(v,TASK_SCHEMA_VERSION,name='task schema');tid=data.get('task_id');obj=data.get('objective');reason=data.get('reason','')
        if not isinstance(tid,str) or not tid:raise ValueError('task_id must be a non-empty string')
        if not isinstance(obj,str) or not obj:raise ValueError('objective must be a non-empty string')
        if not isinstance(reason,str):raise ValueError('reason must be a string')
        ds=data.get('desired_state',{});ops=data.get('operations',[]);succ=data.get('success_when',[]);abort=data.get('abort_if',[])
        if not isinstance(ds,dict) or not isinstance(ops,list) or not isinstance(succ,list) or not isinstance(abort,list):raise ValueError('invalid task fields')
        return cls(tid,obj,reason,dict(ds),[ToolCall.from_dict(x) for x in ops],[Condition.from_dict(x) for x in succ],[Condition.from_dict(x) for x in abort],dict(data.get('current_state',{}) or {}),dict(data.get('remaining',{}) or {}),str(data.get('status','pending')),int(data.get('cursor',0)),int(data.get('failures',0)),int(data.get('replans',0)),v)
    def to_dict(self):return {'task_schema_version':self.task_schema_version,'task_id':self.task_id,'objective':self.objective,'reason':self.reason,'desired_state':self.desired_state,'operations':[asdict(x) for x in self.operations],'success_when':[asdict(x) for x in self.success_when],'abort_if':[asdict(x) for x in self.abort_if],'current_state':self.current_state,'remaining':self.remaining,'status':self.status,'cursor':self.cursor,'failures':self.failures,'replans':self.replans}
@dataclass(slots=True)
class MasterPlan:
    long_term:str|None=None;mid_term:str|None=None;current:str|None=None;next:str|None=None;watch:list[str]=field(default_factory=list);version:int=1
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,data):return cls(data.get('long_term'),data.get('mid_term'),data.get('current'),data.get('next'),list(data.get('watch',[]) or []),int(data.get('version',1)))
@dataclass(slots=True)
class Decision:
    decision:str;task:TaskSpec|None=None;plan_patch:dict[str,Any]=field(default_factory=dict);reason:str|None=None;output_schema_version:str='1.1';prompt_version:str=PROMPT_VERSION
    @classmethod
    def from_dict(cls,data):
        _reject_unknown(data,{'decision','task','plan_patch','reason','output_schema_version','prompt_version'},where='Decision');kind=data.get('decision')
        if kind not in {'create_task','continue','safe_stop'}:raise ValueError('decision must be create_task, continue, or safe_stop')
        task=None
        if kind=='create_task':
            raw=data.get('task')
            if not isinstance(raw,dict):raise ValueError('create_task requires task object')
            task=TaskSpec.from_dict(raw)
        patch=data.get('plan_patch',{}) or {}
        if not isinstance(patch,dict):raise ValueError('plan_patch must be an object')
        reason=data.get('reason')
        if reason is not None and not isinstance(reason,str):raise ValueError('reason must be a string or null')
        return cls(kind,task,dict(patch),reason,str(data.get('output_schema_version','1.1')),str(data.get('prompt_version',PROMPT_VERSION)))
