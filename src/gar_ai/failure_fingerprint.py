from __future__ import annotations
from dataclasses import asdict,dataclass,field
from pathlib import Path
from typing import Any,Mapping
import hashlib,json,os
def _canon(v:Any)->str:return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str)
def environment_hash(environment:Mapping[str,Any])->str:return hashlib.sha256(_canon(environment).encode()).hexdigest()
def recovery_signature(recovery:Mapping[str,Any]|str)->str:return hashlib.sha256((recovery if isinstance(recovery,str) else _canon(recovery)).encode()).hexdigest()
@dataclass(slots=True)
class FailureFingerprint:
    fingerprint:str;task_id:str;task_type:str;tool:str;target:str|None;position:list[float]|None;environment_hash:str;reason_code:str;evidence:dict[str,Any];attempted_recoveries:list[str]=field(default_factory=list);attempts:int=1
    @classmethod
    def build(cls,*,task_id:str,task_type:str,tool:str,target:str|None,position:list[float]|None,environment:Mapping[str,Any],reason_code:str,evidence:Mapping[str,Any]|None=None)->"FailureFingerprint":
        eh=environment_hash(environment);key={'task_type':task_type,'tool':tool,'target':target,'position':position,'environment_hash':eh,'reason_code':reason_code};fp=hashlib.sha256(_canon(key).encode()).hexdigest();return cls(fp,task_id,task_type,tool,target,position,eh,reason_code,dict(evidence or {}))
    def to_dict(self)->dict[str,Any]:return asdict(self)
    @classmethod
    def from_dict(cls,d:Mapping[str,Any])->"FailureFingerprint":return cls(str(d['fingerprint']),str(d['task_id']),str(d['task_type']),str(d['tool']),d.get('target'),None if d.get('position') is None else [float(x) for x in d['position']],str(d['environment_hash']),str(d['reason_code']),dict(d.get('evidence',{}) or {}),list(d.get('attempted_recoveries',[]) or []),int(d.get('attempts',1)))
class FailureFingerprintStore:
    def __init__(self,path:str|Path|None=None)->None:self.path=Path(path) if path is not None else None;self.items={};self._load()
    def _load(self):
        if self.path is not None and self.path.exists():self.items={x['fingerprint']:FailureFingerprint.from_dict(x) for x in json.loads(self.path.read_text(encoding='utf-8'))}
    def _save(self):
        if self.path is None:return
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix(self.path.suffix+'.tmp');tmp.write_text(json.dumps([x.to_dict() for x in self.items.values()],ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8');os.replace(tmp,self.path)
    def record(self,item:FailureFingerprint)->FailureFingerprint:
        old=self.items.get(item.fingerprint)
        if old:old.attempts+=1;old.evidence=item.evidence;self._save();return old
        self.items[item.fingerprint]=item;self._save();return item
    def mark_recovery(self,fingerprint:str,recovery:Mapping[str,Any]|str)->str:
        item=self.items[fingerprint];sig=recovery_signature(recovery)
        if sig not in item.attempted_recoveries:item.attempted_recoveries.append(sig);self._save()
        return sig
    def should_reject_recovery(self,fingerprint:str,recovery:Mapping[str,Any]|str,*,current_environment:Mapping[str,Any])->bool:
        item=self.items.get(fingerprint)
        return bool(item and environment_hash(current_environment)==item.environment_hash and recovery_signature(recovery) in item.attempted_recoveries)
