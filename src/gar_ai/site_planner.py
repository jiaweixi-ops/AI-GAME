from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Iterable,Mapping
import math
from .coordination import Footprint
@dataclass(slots=True)
class SiteCandidate:origin_x:float;origin_y:float;footprint:Footprint;score:float;natural_obstacles:int;player_entity_conflicts:int;reason:str=''
class SitePlanner:
    def score(self,footprint:Footprint,snapshot:Mapping[str,Any],*,origin_x:float,origin_y:float,preferred_x:float|None=None,preferred_y:float|None=None)->SiteCandidate:
        natural=0;conflicts=0
        for e in snapshot.get('entities',[]) or []:
            pos=e.get('position') or [None,None]
            if len(pos)<2 or None in pos:continue
            x,y=float(pos[0]),float(pos[1])
            if not(footprint.x1<=x<=footprint.x2 and footprint.y1<=y<=footprint.y2):continue
            if e.get('natural') or e.get('type') in {'tree','simple-entity','cliff'}:natural+=1
            else:conflicts+=1
        dist=math.dist((origin_x,origin_y),(preferred_x,preferred_y)) if preferred_x is not None and preferred_y is not None else 0.0;score=100-1000*conflicts-3*natural-.1*dist;return SiteCandidate(origin_x,origin_y,footprint,score,natural,conflicts,'ok' if conflicts==0 else 'player_entity_conflict')
    def choose(self,candidates:Iterable[SiteCandidate])->SiteCandidate:
        viable=[x for x in candidates if x.player_entity_conflicts==0]
        if not viable:raise RuntimeError('no viable site without player-entity conflict')
        return max(viable,key=lambda x:x.score)
