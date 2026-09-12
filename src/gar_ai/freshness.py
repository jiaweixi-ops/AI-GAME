from __future__ import annotations
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from typing import Any,Mapping
import time
@dataclass(slots=True)
class EvidenceStamp:
    game_tick:int|None;observed_at_epoch:float;observed_at:str
    @classmethod
    def now(cls,*,game_tick:int|None=None,clock=time.time)->"EvidenceStamp":
        ts=float(clock());return cls(game_tick,ts,datetime.fromtimestamp(ts,tz=timezone.utc).isoformat())
    def to_dict(self)->dict[str,Any]:return asdict(self)
class StaleStateError(RuntimeError):pass
def _tick(v:Any)->int|None:
    try:return int(v) if v is not None else None
    except (TypeError,ValueError):return None
def stamp_snapshot(snapshot:Mapping[str,Any],*,clock=time.time)->dict[str,Any]:
    copied=dict(snapshot);copied['_evidence']=EvidenceStamp.now(game_tick=_tick(snapshot.get('game_tick')),clock=clock).to_dict();return copied
def evidence_age_sec(data:Mapping[str,Any],*,clock=time.time)->float|None:
    ev=data.get('_evidence') if isinstance(data,Mapping) else None
    if not isinstance(ev,Mapping):return None
    try:return max(0.0,float(clock())-float(ev['observed_at_epoch']))
    except (KeyError,TypeError,ValueError):return None
def ensure_fresh(data:Mapping[str,Any],*,max_age_sec:float,current_game_tick:int|None=None,max_tick_lag:int|None=None,clock=time.time)->None:
    age=evidence_age_sec(data,clock=clock)
    if age is None or age>max_age_sec:raise StaleStateError(f"state stale by wall clock: age={age}, limit={max_age_sec}")
    if current_game_tick is not None and max_tick_lag is not None:
        ev=data.get('_evidence') or {};tick=_tick(ev.get('game_tick')) if isinstance(ev,Mapping) else None
        if tick is None or current_game_tick-tick>max_tick_lag:raise StaleStateError(f"state stale by tick: tick={tick}, current={current_game_tick}, limit={max_tick_lag}")
