from datetime import date
from typing import Optional

from pydantic import BaseModel


class OutcomeCheckpointCreateAttributes(BaseModel):
    checkpoint: str
    dimension: str
    value: Optional[str] = None
    source: str
    event_date: date
    is_manual: Optional[bool] = True


class OutcomeCheckpointCreateRequest(BaseModel):
    class Data(BaseModel):
        type: Optional[str] = None
        attributes: OutcomeCheckpointCreateAttributes

    data: Data


class OutcomeDecisionAttributes(BaseModel):
    action: str
    governance_ack: bool
    reason_code: Optional[str] = None
    note: Optional[str] = None


class OutcomeDecisionRequest(BaseModel):
    class Data(BaseModel):
        type: Optional[str] = None
        attributes: OutcomeDecisionAttributes

    data: Data


class CloseRequestAttributes(BaseModel):
    governance_ack: Optional[bool] = None
    reason_code: Optional[str] = None


class CloseRequest(BaseModel):
    class Data(BaseModel):
        attributes: Optional[CloseRequestAttributes] = None

    data: Optional[Data] = None
