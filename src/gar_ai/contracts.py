from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import json

TOOL_SCHEMA_VERSION="1.1"; DIGEST_SCHEMA_VERSION="1.1"; TASK_SCHEMA_VERSION="1.1"; PROMPT_VERSION="factorio-planner-v1.1"; BLUEPRINT_IR_VERSION="0.1"; ERROR_SCHEMA_VERSION="1.0"; CONTRACT_PROBE_SCHEMA_VERSION="1.0"
class SchemaVersionError(ValueError): pass
def _major(version:str)->str:return str(version).split('.',1)[0]
def require_compatible(actual:str,expected:str,*,name:str)->None:
    if not actual: raise SchemaVersionError(f"{name} version missing")
    if _major(actual)!=_major(expected): raise SchemaVersionError(f"{name} version incompatible: got {actual}, expected major {_major(expected)}")
@dataclass(slots=True)
class SchemaVersions:
    tool_schema_version:str=TOOL_SCHEMA_VERSION; digest_schema_version:str=DIGEST_SCHEMA_VERSION; task_schema_version:str=TASK_SCHEMA_VERSION; prompt_version:str=PROMPT_VERSION; blueprint_ir_version:str=BLUEPRINT_IR_VERSION; error_schema_version:str=ERROR_SCHEMA_VERSION
    def to_dict(self)->dict[str,str]:return asdict(self)
@dataclass(slots=True)
class ContractProbeRecord:
    primitive:str; game_version:str; bridge_version:str; mod_set_hash:str|None; status:str; evidence:dict[str,Any]; schema_version:str=CONTRACT_PROBE_SCHEMA_VERSION; probed_at:str=""
    def __post_init__(self)->None:
        if not self.probed_at:self.probed_at=datetime.now(timezone.utc).isoformat()
        if self.status not in {"pass","fail","unknown"}:raise ValueError("status must be pass/fail/unknown")
    def to_dict(self)->dict[str,Any]:return asdict(self)
    @classmethod
    def from_dict(cls,data:Mapping[str,Any])->"ContractProbeRecord":
        require_compatible(str(data.get("schema_version","")),CONTRACT_PROBE_SCHEMA_VERSION,name="contract probe")
        return cls(str(data["primitive"]),str(data["game_version"]),str(data["bridge_version"]),data.get("mod_set_hash"),str(data["status"]),dict(data.get("evidence",{}) or {}),str(data.get("schema_version",CONTRACT_PROBE_SCHEMA_VERSION)),str(data.get("probed_at","")))
class ContractProbeRegistry:
    def __init__(self,path:str|Path)->None:self.path=Path(path)
    def load(self)->list[ContractProbeRecord]:
        if not self.path.exists():return []
        return [ContractProbeRecord.from_dict(x) for x in json.loads(self.path.read_text(encoding="utf-8"))]
    def save(self,records:list[ContractProbeRecord])->None:
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix(self.path.suffix+".tmp"); tmp.write_text(json.dumps([r.to_dict() for r in records],ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8"); tmp.replace(self.path)
    def record(self,record:ContractProbeRecord)->None:
        records=[r for r in self.load() if not (r.primitive==record.primitive and r.game_version==record.game_version and r.bridge_version==record.bridge_version and r.mod_set_hash==record.mod_set_hash)]; records.append(record); self.save(records)
    def assert_passed(self,primitive:str,*,game_version:str,bridge_version:str,mod_set_hash:str|None)->None:
        for r in reversed(self.load()):
            if r.primitive==primitive and r.game_version==game_version and r.bridge_version==bridge_version and r.mod_set_hash==mod_set_hash:
                if r.status!="pass":raise RuntimeError(f"contract probe not passed for {primitive}: {r.status}")
                return
        raise RuntimeError(f"no contract probe record for {primitive}")
