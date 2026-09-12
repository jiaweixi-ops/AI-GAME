from __future__ import annotations
from dataclasses import asdict,dataclass,field
from pathlib import Path
from typing import Any,Mapping
import json,os,time
@dataclass(frozen=True,slots=True)
class Footprint:
    x1:float;y1:float;x2:float;y2:float
    def __post_init__(self):
        if self.x2<=self.x1 or self.y2<=self.y1:raise ValueError('invalid footprint')
    def intersects(self,o:'Footprint')->bool:return not(self.x2<=o.x1 or o.x2<=self.x1 or self.y2<=o.y1 or o.y2<=self.y1)
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d:Mapping[str,Any])->'Footprint':return cls(float(d['x1']),float(d['y1']),float(d['x2']),float(d['y2']))
@dataclass(slots=True)
class AreaLock:
    lock_id:str;task_id:str;footprint:Footprint;acquired_at_epoch:float;expires_at_epoch:float|None=None
    def expired(self,now:float)->bool:return self.expires_at_epoch is not None and now>=self.expires_at_epoch
    def to_dict(self):return {'lock_id':self.lock_id,'task_id':self.task_id,'footprint':self.footprint.to_dict(),'acquired_at_epoch':self.acquired_at_epoch,'expires_at_epoch':self.expires_at_epoch}
    @classmethod
    def from_dict(cls,d):return cls(str(d['lock_id']),str(d['task_id']),Footprint.from_dict(d['footprint']),float(d['acquired_at_epoch']),None if d.get('expires_at_epoch') is None else float(d['expires_at_epoch']))
class AreaLockConflict(RuntimeError):pass
class AreaLockManager:
    def __init__(self,path:str|Path|None=None,*,clock=time.time):self.path=Path(path) if path is not None else None;self.clock=clock;self._locks={};self._load()
    def _load(self):
        if self.path is None or not self.path.exists():return
        self._locks={x['lock_id']:AreaLock.from_dict(x) for x in json.loads(self.path.read_text(encoding='utf-8'))};self._purge()
    def _save(self):
        if self.path is None:return
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix(self.path.suffix+'.tmp');tmp.write_text(json.dumps([x.to_dict() for x in self._locks.values()],ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8');os.replace(tmp,self.path)
    def _purge(self):
        now=self.clock();expired=[k for k,v in self._locks.items() if v.expired(now)]
        for k in expired:self._locks.pop(k,None)
        if expired:self._save()
    def acquire(self,*,lock_id:str,task_id:str,footprint:Footprint,ttl_sec:float|None=None)->AreaLock:
        self._purge();old=self._locks.get(lock_id)
        if old and old.task_id==task_id and old.footprint==footprint:return old
        for lock in self._locks.values():
            if lock.task_id!=task_id and lock.footprint.intersects(footprint):raise AreaLockConflict(f'area overlaps lock {lock.lock_id} owned by {lock.task_id}')
        now=self.clock();lock=AreaLock(lock_id,task_id,footprint,now,None if ttl_sec is None else now+ttl_sec);self._locks[lock_id]=lock;self._save();return lock
    def release(self,lock_id:str,*,task_id:str|None=None)->bool:
        lock=self._locks.get(lock_id)
        if lock is None:return False
        if task_id is not None and lock.task_id!=task_id:raise PermissionError('lock owned by another task')
        self._locks.pop(lock_id,None);self._save();return True
    def locks(self)->list[AreaLock]:self._purge();return list(self._locks.values())
@dataclass(slots=True)
class MaterialReservation:
    reservation_id:str;task_id:str;requested:dict[str,int];consumed:dict[str,int]=field(default_factory=dict);released:dict[str,int]=field(default_factory=dict);status:str='reserved'
    def remaining(self,item:str)->int:return max(0,self.requested.get(item,0)-self.consumed.get(item,0)-self.released.get(item,0))
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d):return cls(str(d['reservation_id']),str(d['task_id']),{str(k):int(v) for k,v in dict(d.get('requested',{})).items()},{str(k):int(v) for k,v in dict(d.get('consumed',{})).items()},{str(k):int(v) for k,v in dict(d.get('released',{})).items()},str(d.get('status','reserved')))
class MaterialReservationError(RuntimeError):pass
class MaterialReservationManager:
    def __init__(self,path:str|Path|None=None):self.path=Path(path) if path is not None else None;self._reservations={};self._load()
    def _load(self):
        if self.path is not None and self.path.exists():self._reservations={x['reservation_id']:MaterialReservation.from_dict(x) for x in json.loads(self.path.read_text(encoding='utf-8'))}
    def _save(self):
        if self.path is None:return
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix(self.path.suffix+'.tmp');tmp.write_text(json.dumps([x.to_dict() for x in self._reservations.values()],ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8');os.replace(tmp,self.path)
    def reserved_totals(self,*,exclude_reservation:str|None=None)->dict[str,int]:
        totals={}
        for rid,r in self._reservations.items():
            if rid==exclude_reservation or r.status not in {'reserved','partial'}:continue
            for item in r.requested:totals[item]=totals.get(item,0)+r.remaining(item)
        return totals
    def reserve(self,*,reservation_id:str,task_id:str,requested:Mapping[str,int],available:Mapping[str,int])->MaterialReservation:
        clean={str(k):int(v) for k,v in requested.items() if int(v)>0};old=self._reservations.get(reservation_id)
        if old:
            if old.task_id!=task_id or old.requested!=clean:raise MaterialReservationError('reservation id already used with different content')
            return old
        reserved=self.reserved_totals();short={i:n for i,n in clean.items() if int(available.get(i,0))-reserved.get(i,0)<n}
        if short:raise MaterialReservationError(f'insufficient available materials: {short}')
        r=MaterialReservation(reservation_id,task_id,clean);self._reservations[reservation_id]=r;self._save();return r
    def consume(self,reservation_id:str,item:str,count:int)->None:
        r=self._reservations[reservation_id];count=int(count)
        if count<0 or count>r.remaining(item):raise MaterialReservationError('consume exceeds reservation')
        r.consumed[item]=r.consumed.get(item,0)+count;r.status='partial' if any(r.remaining(x)>0 for x in r.requested) else 'consumed';self._save()
    def release(self,reservation_id:str)->dict[str,int]:
        r=self._reservations[reservation_id];rel={i:r.remaining(i) for i in r.requested if r.remaining(i)>0}
        for i,c in rel.items():r.released[i]=r.released.get(i,0)+c
        if r.status!='consumed':r.status='released'
        self._save();return rel
    def get(self,reservation_id:str):return self._reservations.get(reservation_id)
