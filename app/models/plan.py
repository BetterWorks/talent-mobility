from datetime import date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class PlanPatchAttributes(BaseModel):
    duration_weeks: Optional[int] = None
    start_date: Optional[date] = None
    owner_id: Optional[str] = None
    readiness_target: Optional[str] = None


class PlanWeekWriteAttributes(BaseModel):
    week_no: Optional[int] = None
    label: Optional[str] = None
    focus: Optional[str] = None
    goal: Optional[str] = None
    one_on_one: Optional[str] = None
    learning: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    position: Optional[int] = None


class PlanWeekWrite(BaseModel):
    type: Optional[str] = None
    id: Optional[UUID] = None
    attributes: PlanWeekWriteAttributes


class PlanPatchRequest(BaseModel):
    class Data(BaseModel):
        type: Optional[str] = None
        attributes: Optional[PlanPatchAttributes] = None
        weeks: Optional[List[PlanWeekWrite]] = None

    data: Data


class PlanGenerateAttributes(BaseModel):
    duration_weeks: Optional[int] = None


class PlanGenerateRequest(BaseModel):
    class Data(BaseModel):
        type: Optional[str] = None
        attributes: Optional[PlanGenerateAttributes] = None

    data: Optional[Data] = None
