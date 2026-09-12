from __future__ import annotations
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Mapping
import json
@dataclass(slots=True)
class JournalEntry:
    task_id:str;batch_id:str;operation_id:str;phase:str;status:str;side_effect:str;detail:dict[str,Any];timestamp:str
    @classmethod
    def create(cls,*,task_id:str,batch_id:str,operation_id:str,phase:str,status:str,side_effect:str,detail:Mapping[str,Any]|None=None):return cls(task_id,batch_id,operation_id,phase,status,side_effect,dict(detail or {}),datetime.now(timezone.utc).isoformat())
class OperationJournal:
    def __init__(self,path:str|Path):self.path=Path(path)
    def append(self,entry:JournalEntry):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(asdict(entry),ensure_ascii=False,sort_keys=True)+'\n')
    def entries(self):
        if not self.path.exists():return []
        return [json.loads(x) for x in self.path.read_text(encoding='utf-8').splitlines() if x.strip()]
    def has_committed(self,operation_id:str)->bool:return any(x.get('operation_id')==operation_id and x.get('status')=='committed' for x in self.entries())
