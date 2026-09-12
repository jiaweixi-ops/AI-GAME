from __future__ import annotations
from dataclasses import asdict,dataclass,field
from enum import Enum
from typing import Any,Callable,Mapping
import time
class AsyncVerificationStatus(str,Enum):PENDING='pending';VERIFIED='verified';TIMEOUT='timeout';FAILED='failed'
@dataclass(slots=True)
class AsyncVerificationSpec:verification_id:str;deadline_sec:float=30.0;poll_interval_sec:float=0.5;stable_polls:int=1
@dataclass(slots=True)
class PendingVerification:
    spec:AsyncVerificationSpec;started_at:float;last_poll_at:float|None=None;successful_polls:int=0;polls:int=0;status:AsyncVerificationStatus=AsyncVerificationStatus.PENDING;evidence:dict[str,Any]=field(default_factory=dict)
    def to_dict(self)->dict[str,Any]:d=asdict(self);d['status']=self.status.value;return d
class AsyncVerifier:
    def __init__(self,snapshot:Callable[[],Mapping[str,Any]],*,clock=time.monotonic)->None:self.snapshot=snapshot;self.clock=clock
    def start(self,spec:AsyncVerificationSpec)->PendingVerification:
        if spec.deadline_sec<=0 or spec.poll_interval_sec<0 or spec.stable_polls<1:raise ValueError('invalid async verification spec')
        return PendingVerification(spec=spec,started_at=self.clock())
    def poll_once(self,pending:PendingVerification,predicate:Callable[[Mapping[str,Any]],tuple[bool,Mapping[str,Any]]])->PendingVerification:
        if pending.status is not AsyncVerificationStatus.PENDING:return pending
        now=self.clock()
        if now-pending.started_at>pending.spec.deadline_sec:pending.status=AsyncVerificationStatus.TIMEOUT;return pending
        if pending.last_poll_at is not None and now-pending.last_poll_at<pending.spec.poll_interval_sec:return pending
        snap=self.snapshot();pending.polls+=1;pending.last_poll_at=now
        try:ok,evidence=predicate(snap)
        except Exception as exc:pending.status=AsyncVerificationStatus.FAILED;pending.evidence={'error':repr(exc)};return pending
        pending.evidence=dict(evidence);pending.successful_polls=pending.successful_polls+1 if ok else 0
        if pending.successful_polls>=pending.spec.stable_polls:pending.status=AsyncVerificationStatus.VERIFIED
        return pending
