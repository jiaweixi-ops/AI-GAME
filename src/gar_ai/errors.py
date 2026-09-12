from __future__ import annotations
from dataclasses import asdict,dataclass
from enum import Enum
from typing import Any
from .contracts import ERROR_SCHEMA_VERSION
class ErrorCode(str,Enum):
    ACK_REJECTED="ACK_REJECTED";FRESH_STATE_UNVERIFIED="FRESH_STATE_UNVERIFIED";PENDING="PENDING";VERIFY_TIMEOUT="VERIFY_TIMEOUT";TOOL_FAILED="TOOL_FAILED";STRATEGY_REVIEW_REQUIRED="REJECTED_FOR_STRATEGY_REVIEW";ATOMIC_BUDGET_EXCEEDED="ATOMIC_BUDGET_EXCEEDED";TASK_BUDGET_EXCEEDED="TASK_BUDGET_EXCEEDED";BATCH_BUDGET_EXCEEDED="BATCH_BUDGET_EXCEEDED";GLOBAL_BUDGET_EXCEEDED="GLOBAL_BUDGET_EXCEEDED";REPLAN_BUDGET_EXCEEDED="REPLAN_BUDGET_EXCEEDED";STALE_STATE="STALE_STATE";AREA_LOCK_CONFLICT="AREA_LOCK_CONFLICT";MATERIAL_RESERVATION_FAILED="MATERIAL_RESERVATION_FAILED";SCHEMA_INCOMPATIBLE="SCHEMA_INCOMPATIBLE";UNKNOWN_ABORT_PATH="UNKNOWN_ABORT_PATH";SAFE_STOP="SAFE_STOP"
@dataclass(frozen=True,slots=True)
class ErrorPolicy: retryable:bool;write_failure_history:bool;trigger_ai:bool;safe_stop:bool=False
ERROR_POLICIES={ErrorCode.ACK_REJECTED:ErrorPolicy(True,True,True),ErrorCode.FRESH_STATE_UNVERIFIED:ErrorPolicy(True,True,True),ErrorCode.PENDING:ErrorPolicy(False,False,False),ErrorCode.VERIFY_TIMEOUT:ErrorPolicy(False,True,True),ErrorCode.TOOL_FAILED:ErrorPolicy(True,True,True),ErrorCode.STRATEGY_REVIEW_REQUIRED:ErrorPolicy(False,True,True),ErrorCode.ATOMIC_BUDGET_EXCEEDED:ErrorPolicy(False,True,True),ErrorCode.TASK_BUDGET_EXCEEDED:ErrorPolicy(False,True,True),ErrorCode.BATCH_BUDGET_EXCEEDED:ErrorPolicy(False,True,True),ErrorCode.GLOBAL_BUDGET_EXCEEDED:ErrorPolicy(False,True,True,True),ErrorCode.REPLAN_BUDGET_EXCEEDED:ErrorPolicy(False,True,False,True),ErrorCode.STALE_STATE:ErrorPolicy(True,False,False),ErrorCode.AREA_LOCK_CONFLICT:ErrorPolicy(True,True,True),ErrorCode.MATERIAL_RESERVATION_FAILED:ErrorPolicy(True,True,True),ErrorCode.SCHEMA_INCOMPATIBLE:ErrorPolicy(False,True,False,True),ErrorCode.UNKNOWN_ABORT_PATH:ErrorPolicy(False,True,True),ErrorCode.SAFE_STOP:ErrorPolicy(False,True,False,True)}
@dataclass(slots=True)
class ErrorEnvelope:
    code:ErrorCode;message:str;detail:dict[str,Any];schema_version:str=ERROR_SCHEMA_VERSION
    def to_dict(self)->dict[str,Any]:d=asdict(self);d['code']=self.code.value;return d
