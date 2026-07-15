from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, Field, SQLModel

from app.db import meta
from app.utils.common import get_utc_now


class RunAiMatchesStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


class RunAiMatchesBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    request_id: Optional[UUID] = Field(default=None)
    status: Optional[str] = Field(default=RunAiMatchesStatus.PENDING.value)


class RunAiMatches(RunAiMatchesBase, table=True):
    __tablename__ = 'run_ai_matches'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class RunAiMatchesDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: RunAiMatchesBase) -> RunAiMatches:
        new_run = RunAiMatches(**data.model_dump())
        self.session.add(new_run)
        await self.session.commit()
        await self.session.refresh(new_run)
        return new_run

    async def get_by_id(self, run_id: UUID) -> Optional[RunAiMatches]:
        result = await self.session.execute(
            select(RunAiMatches).where(RunAiMatches.id == run_id)
        )
        return result.scalars().first()

    async def get_latest_by_request(self, request_id: UUID) -> Optional[RunAiMatches]:
        result = await self.session.execute(
            select(RunAiMatches).where(
                RunAiMatches.request_id == request_id
            ).order_by(RunAiMatches.created.desc())
        )
        return result.scalars().first()

    async def update(self, run_id: UUID, **kwargs) -> Optional[RunAiMatches]:
        kwargs['modified'] = kwargs.get('modified') or get_utc_now(tz=False)
        statement = (
            update(RunAiMatches).
            returning(RunAiMatches).
            where(RunAiMatches.id == run_id).
            values(**kwargs)
        )
        result = await self.session.execute(statement=statement)
        await self.session.commit()
        return result.scalars().first()
