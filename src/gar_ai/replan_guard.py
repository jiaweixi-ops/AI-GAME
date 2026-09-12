from __future__ import annotations
from dataclasses import asdict,dataclass,field
from pathlib import Path
import json,os,time
@dataclass(slots=True)
class ReplanPolicy:min_interval_sec:float=30.0;window_sec:float=600.0;max_per_window:int=4
@dataclass(slots=True)
class ReplanState:timestamps:list[float]=field(default_factory=list)
class ReplanGuard:
    def __init__(self,path:str|Path|None=None,*,policy:ReplanPolicy|None=None,clock=time.time):self.path=Path(path) if path is not None else None;self.policy=policy or ReplanPolicy();self.clock=clock;self.state=ReplanState();self._load()
    def _load(self):
        if self.path is not None and self.path.exists():self.state=ReplanState(**json.loads(self.path.read_text(encoding='utf-8')))
    def _save(self):
        if self.path is None:return
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix(self.path.suffix+'.tmp');tmp.write_text(json.dumps(asdict(self.state),indent=2),encoding='utf-8');os.replace(tmp,self.path)
    def _prune(self,now):self.state.timestamps=[x for x in self.state.timestamps if now-x<=self.policy.window_sec]
    def allowed(self):
        now=self.clock();self._prune(now)
        if self.state.timestamps and now-self.state.timestamps[-1]<self.policy.min_interval_sec:return False,'replan_min_interval'
        if len(self.state.timestamps)>=self.policy.max_per_window:return False,'replan_window_limit'
        return True,None
    def record(self):
        ok,reason=self.allowed()
        if not ok:raise RuntimeError(reason)
        self.state.timestamps.append(self.clock());self._save()
