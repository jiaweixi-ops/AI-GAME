from __future__ import annotations
from dataclasses import asdict,dataclass,field
from typing import Any,Mapping
from .contracts import BLUEPRINT_IR_VERSION,require_compatible
from .coordination import Footprint
@dataclass(frozen=True,slots=True)
class EntityPlacement:
    entity_id:str;name:str;x:float;y:float;direction:int|None=None;role:str|None=None
    def to_tool_args(self):
        out={'name':self.name,'x':self.x,'y':self.y}
        if self.direction is not None:out['direction']=self.direction
        return out
@dataclass(frozen=True,slots=True)
class Port:name:str;kind:str;x:float;y:float;direction:str;item:str|None=None
@dataclass(slots=True)
class BlueprintIR:
    blueprint_id:str;module_type:str;footprint:Footprint;entities:list[EntityPlacement];input_ports:list[Port];output_ports:list[Port];power_ports:list[Port];expansion_ports:list[Port];required_items:dict[str,int];clearance:dict[str,float];metadata:dict[str,Any]=field(default_factory=dict);blueprint_ir_version:str=BLUEPRINT_IR_VERSION
    def validate(self):
        require_compatible(self.blueprint_ir_version,BLUEPRINT_IR_VERSION,name='blueprint_ir');ids=[e.entity_id for e in self.entities]
        if len(ids)!=len(set(ids)):raise ValueError('duplicate entity_id')
        if not self.entities:raise ValueError('blueprint has no entities')
        for item,count in self.required_items.items():
            if not item or int(count)<0:raise ValueError('invalid required_items')
        for e in self.entities:
            if not(self.footprint.x1<=e.x<=self.footprint.x2 and self.footprint.y1<=e.y<=self.footprint.y2):raise ValueError(f'entity {e.entity_id} outside footprint')
    def to_dict(self):
        self.validate();return {'blueprint_ir_version':self.blueprint_ir_version,'blueprint_id':self.blueprint_id,'module_type':self.module_type,'footprint':self.footprint.to_dict(),'entities':[asdict(x) for x in self.entities],'input_ports':[asdict(x) for x in self.input_ports],'output_ports':[asdict(x) for x in self.output_ports],'power_ports':[asdict(x) for x in self.power_ports],'expansion_ports':[asdict(x) for x in self.expansion_ports],'required_items':dict(self.required_items),'clearance':dict(self.clearance),'metadata':dict(self.metadata)}
    @classmethod
    def from_dict(cls,d:Mapping[str,Any])->'BlueprintIR':
        v=str(d.get('blueprint_ir_version',''));require_compatible(v,BLUEPRINT_IR_VERSION,name='blueprint_ir');o=cls(str(d['blueprint_id']),str(d['module_type']),Footprint.from_dict(d['footprint']),[EntityPlacement(**x) for x in d.get('entities',[])],[Port(**x) for x in d.get('input_ports',[])],[Port(**x) for x in d.get('output_ports',[])],[Port(**x) for x in d.get('power_ports',[])],[Port(**x) for x in d.get('expansion_ports',[])],{str(k):int(v) for k,v in dict(d.get('required_items',{})).items()},{str(k):float(v) for k,v in dict(d.get('clearance',{})).items()},dict(d.get('metadata',{}) or {}),v);o.validate();return o
