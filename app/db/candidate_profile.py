from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.mutable import MutableDict
from sqlmodel import Column, Field, SQLModel

from app.db import meta
from app.utils.common import get_utc_now


class CandidateProfileStatus(IntEnum):
    PENDING = 0
    MATCHED = 1
    APPROVED = 2
    HOLD = 3
    REJECTED = 4
    DECISION = 5


class CandidateProfileBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)

    user_uuid: UUID = Field()
    org_uuid: UUID = Field()
    org_id: Optional[int] = Field(default=None)
    user_id: Optional[int] = Field(default=None)

    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    run_ai_match: Optional[UUID] = Field(default=None)

    profile_data: Optional[dict] = Field(default=None)
    status: int = Field(default=CandidateProfileStatus.PENDING.value)


class CandidateProfile(CandidateProfileBase, table=True):
    __tablename__ = 'candidate_profile'
    metadata = meta
    profile_data: Optional[dict] = Field(default=None, sa_column=Column(MutableDict.as_mutable(JSONB)))

    class Config:
        arbitrary_types_allowed = True


class CandidateProfileDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: CandidateProfileBase) -> CandidateProfile:
        new_profile = CandidateProfile(**data.model_dump())
        self.session.add(new_profile)
        await self.session.commit()
        await self.session.refresh(new_profile)
        return new_profile

    async def bulk_create(self, data: List[CandidateProfileBase]) -> List[CandidateProfile]:
        new_profiles = [CandidateProfile(**item.model_dump()) for item in data]
        self.session.add_all(new_profiles)
        await self.session.commit()
        for profile in new_profiles:
            await self.session.refresh(profile)
        return new_profiles

    async def get_by_id(self, profile_id: UUID) -> Optional[CandidateProfile]:
        result = await self.session.execute(
            select(CandidateProfile).where(CandidateProfile.id == profile_id)
        )
        return result.scalars().first()

    async def get_by_run(self, run_ai_match: UUID) -> List[CandidateProfile]:
        result = await self.session.execute(
            select(CandidateProfile).where(
                CandidateProfile.run_ai_match == run_ai_match
            ).order_by(CandidateProfile.created.desc())
        )
        return result.scalars().all()

    async def list_by_run(
        self,
        run_ai_match: UUID,
        cost_impact: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = True,
    ) -> List[CandidateProfile]:
        sort_columns = {
            'match_score': CandidateProfile.profile_data['match_score'].astext.cast(Integer),
            'cost_impact': CandidateProfile.profile_data['cost_impact'].astext,
        }
        order_column = sort_columns.get(sort_by, CandidateProfile.created)
        order_clause = order_column.desc() if sort_desc else order_column.asc()

        result = await self.session.execute(
            select(CandidateProfile).where(
                CandidateProfile.run_ai_match == run_ai_match,
                True if cost_impact is None
                else CandidateProfile.profile_data['cost_impact'].astext == cost_impact,
            ).order_by(order_clause)
        )
        return result.scalars().all()

    async def update(self, profile_id: UUID, **kwargs) -> Optional[CandidateProfile]:
        kwargs['modified'] = kwargs.get('modified') or get_utc_now(tz=False)
        statement = (
            update(CandidateProfile).
            returning(CandidateProfile).
            where(CandidateProfile.id == profile_id).
            values(**kwargs)
        )
        result = await self.session.execute(statement=statement)
        await self.session.commit()
        return result.scalars().first()
