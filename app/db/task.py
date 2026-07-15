from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, Field, SQLModel

from app.db import meta
from app.utils.common import get_utc_now


class TaskSyncStatus(str, Enum):
    SYNCED = 'synced'
    PENDING_SYNC = 'pending_sync'
    AWAITING_REVIEW = 'awaiting_review'


class TaskBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    # Logical ref: better_sense.mobility_case.id
    case_id: UUID = Field()

    title: Optional[str] = Field(default=None)
    module: Optional[str] = Field(default=None)
    owner_name: Optional[str] = Field(default=None)
    due_label: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    sync_status: str = Field(default=TaskSyncStatus.SYNCED.value)
    external_ref_id: Optional[str] = Field(default=None)


class Task(TaskBase, table=True):
    __tablename__ = 'task'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class TaskDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_create(self, data: List[TaskBase]) -> List[Task]:
        new_rows = [Task(**item.model_dump()) for item in data]
        self.session.add_all(new_rows)
        await self.session.commit()
        for row in new_rows:
            await self.session.refresh(row)
        return new_rows

    async def get_by_id(self, task_id: UUID) -> Optional[Task]:
        result = await self.session.execute(select(Task).where(Task.id == task_id))
        return result.scalars().first()

    async def list_by_case(self, case_id: UUID) -> List[Task]:
        result = await self.session.execute(
            select(Task).where(Task.case_id == case_id).order_by(Task.created.asc())
        )
        return result.scalars().all()

    async def delete_by_case(self, case_id: UUID) -> None:
        rows = await self.list_by_case(case_id)
        for row in rows:
            await self.session.delete(row)
        await self.session.commit()

    async def update(self, task_id: UUID, **kwargs) -> Optional[Task]:
        kwargs['modified'] = kwargs.get('modified') or get_utc_now(tz=False)
        statement = (
            update(Task).
            returning(Task).
            where(Task.id == task_id).
            values(**kwargs)
        )
        result = await self.session.execute(statement=statement)
        await self.session.commit()
        return result.scalars().first()
