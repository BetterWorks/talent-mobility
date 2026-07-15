from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class ConsentMarkReceivedAttributes(BaseModel):
    by_hr: Optional[bool] = False


class ConsentMarkReceivedRequest(BaseModel):
    class Data(BaseModel):
        type: Optional[str] = None
        attributes: Optional[ConsentMarkReceivedAttributes] = None

    data: Optional[Data] = None


class ConsentDeadlineAttributes(BaseModel):
    deadline: date


class ConsentDeadlineRequest(BaseModel):
    class Data(BaseModel):
        type: Optional[str] = None
        attributes: ConsentDeadlineAttributes

    data: Data


class NotifyCreateAttributes(BaseModel):
    recipient_ids: Optional[List[str]] = None
    message: Optional[str] = None
    channels: Optional[List[str]] = None


class NotifyCreateRequest(BaseModel):
    class Data(BaseModel):
        type: Optional[str] = None
        attributes: Optional[NotifyCreateAttributes] = None

    data: Optional[Data] = None
