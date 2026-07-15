from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, Field, SQLModel

from app.db import meta
from app.utils.common import get_utc_now


class CaseStatus(str, Enum):
    CONSENT_PENDING = 'consent_pending'
    PLANNING = 'planning'
    IN_TRANSITION = 'in_transition'
    AT_RISK = 'at_risk'
    COMPLETED = 'completed'
    CLOSED = 'closed'
    DECLINED = 'declined'
    RELEASE_BLOCKED = 'release_blocked'


class CaseBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    candidate_match_id: UUID = Field()
    role_request_id: UUID = Field()
    decision_id: Optional[UUID] = Field(default=None)
    status: str = Field(default=CaseStatus.CONSENT_PENDING.value)


class Case(CaseBase, table=True):
    # Named `mobility_case`, not `case` — `case` is a reserved SQL keyword and this way the
    # table name matches the `mobility_case` JSON:API resource type discriminator directly.
    __tablename__ = 'mobility_case'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class CaseDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: CaseBase) -> Case:
        new_case = Case(**data.model_dump())
        self.session.add(new_case)
        await self.session.commit()
        await self.session.refresh(new_case)
        return new_case

    async def get_by_id(self, case_id: UUID) -> Optional[Case]:
        result = await self.session.execute(select(Case).where(Case.id == case_id))
        return result.scalars().first()

    async def list_by_statuses(self, statuses: List[str]) -> List[Case]:
        result = await self.session.execute(select(Case).where(Case.status.in_(statuses)))
        return result.scalars().all()

    async def update(self, case_id: UUID, **kwargs) -> Optional[Case]:
        kwargs['modified'] = kwargs.get('modified') or get_utc_now(tz=False)
        statement = (
            update(Case).
            returning(Case).
            where(Case.id == case_id).
            values(**kwargs)
        )
        result = await self.session.execute(statement=statement)
        await self.session.commit()
        return result.scalars().first()
