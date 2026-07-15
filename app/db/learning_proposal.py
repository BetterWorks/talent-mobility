from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, Field, SQLModel

from app.db import meta
from app.utils.common import get_utc_now


class LearningProposalStatus(str, Enum):
    PROPOSED = 'proposed'
    APPROVED_OFFLINE = 'approved_offline'
    REJECTED = 'rejected'


class LearningProposalBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    # Logical ref: better_sense.mobility_case.id — one proposal per case
    case_id: UUID = Field()
    status: str = Field(default=LearningProposalStatus.PROPOSED.value)


class LearningProposal(LearningProposalBase, table=True):
    __tablename__ = 'learning_proposal'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class LearningProposalDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, case_id: UUID) -> LearningProposal:
        result = await self.session.execute(
            select(LearningProposal).where(LearningProposal.case_id == case_id)
        )
        existing = result.scalars().first()
        if existing:
            return existing
        new_row = LearningProposal(case_id=case_id)
        self.session.add(new_row)
        await self.session.commit()
        await self.session.refresh(new_row)
        return new_row

    async def update(self, proposal_id: UUID, **kwargs) -> Optional[LearningProposal]:
        kwargs['modified'] = kwargs.get('modified') or get_utc_now(tz=False)
        statement = (
            update(LearningProposal).
            returning(LearningProposal).
            where(LearningProposal.id == proposal_id).
            values(**kwargs)
        )
        result = await self.session.execute(statement=statement)
        await self.session.commit()
        return result.scalars().first()
