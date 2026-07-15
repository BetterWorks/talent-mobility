from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, Field, SQLModel

from app.db import meta
from app.utils.common import get_utc_now


class DecisionOutcome(str, Enum):
    APPROVE = 'approve'
    HOLD = 'hold'
    REJECT = 'reject'
    PROCEED_EXTERNAL = 'proceed_external'


class DecisionBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    candidate_match_id: UUID = Field()
    outcome: str = Field()
    reason_code: Optional[str] = Field(default=None)
    note: Optional[str] = Field(default=None)
    review_date: Optional[date] = Field(default=None)

    # Logical ref: better_sense.mobility_case.id — set only when outcome == approve.
    case_id: Optional[UUID] = Field(default=None)


class Decision(DecisionBase, table=True):
    __tablename__ = 'decision'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class DecisionDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: DecisionBase) -> Decision:
        new_decision = Decision(**data.model_dump())
        self.session.add(new_decision)
        await self.session.commit()
        await self.session.refresh(new_decision)
        return new_decision

    async def get_latest_by_candidate(self, candidate_match_id: UUID) -> Optional[Decision]:
        result = await self.session.execute(
            select(Decision).where(
                Decision.candidate_match_id == candidate_match_id
            ).order_by(Decision.created.desc())
        )
        return result.scalars().first()

    async def update(self, decision_id: UUID, **kwargs) -> Optional[Decision]:
        kwargs['modified'] = kwargs.get('modified') or get_utc_now(tz=False)
        statement = (
            update(Decision).
            returning(Decision).
            where(Decision.id == decision_id).
            values(**kwargs)
        )
        result = await self.session.execute(statement=statement)
        await self.session.commit()
        return result.scalars().first()
