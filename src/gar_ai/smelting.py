from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from typing import Literal
from .blueprint_ir import BlueprintIR,EntityPlacement,Port
from .coordination import Footprint
FurnaceCount=Literal[8,16,24,48];RowMode=Literal['single-row','double-row'];InputSide=Literal['left','right'];ExpansionDirection=Literal['north','south']
@dataclass(slots=True)
class SmeltingPlanRequest:
    blueprint_id:str;product:str;furnace_count:FurnaceCount;row_mode:RowMode;input_side:InputSide;expansion:ExpansionDirection;origin_x:float=0.0;origin_y:float=0.0;furnace_name:str='stone-furnace';belt_name:str='transport-belt';inserter_name:str='inserter';pole_name:str='small-electric-pole'
class SmeltingPlanner:
    ALLOWED_COUNTS={8,16,24,48}
    def plan(self,req:SmeltingPlanRequest)->BlueprintIR:
        if req.furnace_count not in self.ALLOWED_COUNTS:raise ValueError('furnace_count must be one of 8/16/24/48')
        if req.row_mode not in {'single-row','double-row'} or req.input_side not in {'left','right'} or req.expansion not in {'north','south'}:raise ValueError('invalid smelting layout option')
        rows=[req.furnace_count] if req.row_mode=='single-row' else [req.furnace_count//2,req.furnace_count//2];entities=[];required=Counter();eid=0;ins=[];outs=[];powers=[]
        def add(name,x,y,direction=None,role=None):
            nonlocal eid;eid+=1;entities.append(EntityPlacement(f'e{eid:04d}',name,round(x,3),round(y,3),direction,role));required[name]+=1
        for ri,count in enumerate(rows):
            ry=req.origin_y+ri*9.0;iy=ry-2.0;oy=ry+2.0;sx=req.origin_x;ex=sx+(count-1)*3.0;bs=sx-2;be=ex+2;direction=2 if req.input_side=='left' else 6
            for x in [bs+i for i in range(int(round(be-bs))+1)]:add(req.belt_name,x,iy,direction,'input_belt');add(req.belt_name,x,oy,direction,'output_belt')
            for i in range(count):
                x=sx+i*3.0;add(req.furnace_name,x,ry,role='furnace');add(req.inserter_name,x,ry-1.5,4,'input_inserter');add(req.inserter_name,x,ry+1.5,0,'output_inserter')
                if i%4==0:add(req.pole_name,x+1.25,ry,role='power')
            inx=bs if req.input_side=='left' else be;outx=be if req.input_side=='left' else bs;ins.append(Port(f'input-{ri}','belt',inx,iy,'west' if req.input_side=='left' else 'east','ore+fuel'));outs.append(Port(f'output-{ri}','belt',outx,oy,'east' if req.input_side=='left' else 'west',req.product));powers.append(Port(f'power-{ri}','power',sx+1.25,ry,'any'))
        xs=[e.x for e in entities];ys=[e.y for e in entities];fp=Footprint(min(xs)-1,min(ys)-1,max(xs)+1,max(ys)+1);ey=fp.y1 if req.expansion=='north' else fp.y2
        ir=BlueprintIR(req.blueprint_id,'smelting',fp,entities,ins,outs,powers,[Port('expansion','area',(fp.x1+fp.x2)/2,ey,req.expansion)],dict(required),{'natural_obstacles':1.0,'player_entities':2.0,'future_expansion':3.0},{'product':req.product,'furnace_count':req.furnace_count,'row_mode':req.row_mode,'input_side':req.input_side,'expansion':req.expansion});ir.validate();return ir
