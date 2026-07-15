from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, Field, SQLModel

from app.db import meta
from app.utils.common import get_utc_now


class CheckpointLabel(str, Enum):
    DAY_30 = '30-day'
    DAY_60 = '60-day'
    DAY_90 = '90-day'
    MONTH_6 = '6-month'
    MONTH_12 = '12-month'


class OutcomeCheckpointBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    # Logical ref: better_sense.mobility_case.id
    case_id: UUID = Field()

    checkpoint: str = Field()
    dimension: str = Field()
    value: Optional[str] = Field(default=None)
    source: str = Field()
    event_date: date = Field()
    is_manual: bool = Field(default=True)


class OutcomeCheckpoint(OutcomeCheckpointBase, table=True):
    __tablename__ = 'outcome_checkpoint'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class OutcomeCheckpointDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: OutcomeCheckpointBase) -> OutcomeCheckpoint:
        new_row = OutcomeCheckpoint(**data.model_dump())
        self.session.add(new_row)
        await self.session.commit()
        await self.session.refresh(new_row)
        return new_row

    async def list_by_case(self, case_id: UUID) -> List[OutcomeCheckpoint]:
        result = await self.session.execute(
            select(OutcomeCheckpoint).where(
                OutcomeCheckpoint.case_id == case_id
            ).order_by(OutcomeCheckpoint.event_date.desc())
        )
        return result.scalars().all()
