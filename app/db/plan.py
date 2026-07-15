from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, Field, SQLModel

from app.db import meta
from app.utils.common import get_utc_now


class PlanStatus(str, Enum):
    NONE = 'none'
    DRAFT = 'draft'
    ACTIVE = 'active'
    COMPLETED = 'completed'


class PlanWeekStatus(str, Enum):
    PLANNED = 'planned'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    UPCOMING = 'upcoming'


class PlanActionKind(str, Enum):
    REDIRECT = 'redirect'
    ATTACH = 'attach'


class PlanActionModule(str, Enum):
    GOALS = 'goals'
    ONE_ON_ONES = 'one_on_ones'
    CONVERSATIONS = 'conversations'
    FEEDBACK = 'feedback'
    LEARNING = 'learning'
    RESOURCES = 'resources'


class PlanBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    # Logical ref: better_sense.mobility_case.id — one plan per case
    case_id: UUID = Field()

    status: str = Field(default=PlanStatus.NONE.value)
    ai_generated: bool = Field(default=False)
    duration_weeks: Optional[int] = Field(default=None)
    start_date: Optional[date] = Field(default=None)

    # Denormalized display name (no real user reference — see consent.py's note on the same
    # limitation); defaults to the role request's hiring_manager, who owns the transition plan.
    owner_name: Optional[str] = Field(default=None)

    readiness_target: Optional[str] = Field(default=None)
    initiated_on: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class Plan(PlanBase, table=True):
    __tablename__ = 'plan'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class PlanWeekBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    # Logical ref: better_sense.plan.id
    plan_id: UUID = Field()

    week_no: Optional[int] = Field(default=None)
    label: Optional[str] = Field(default=None)
    focus: Optional[str] = Field(default=None)
    goal: Optional[str] = Field(default=None)
    one_on_one: Optional[str] = Field(default=None)
    learning: Optional[str] = Field(default=None)
    start_date: Optional[date] = Field(default=None)
    end_date: Optional[date] = Field(default=None)
    status: str = Field(default=PlanWeekStatus.UPCOMING.value)
    position: int = Field(default=0)


class PlanWeek(PlanWeekBase, table=True):
    __tablename__ = 'plan_week'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class PlanActionBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    # Logical ref: better_sense.plan.id
    plan_id: UUID = Field()

    title: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    kind: str = Field(default=PlanActionKind.REDIRECT.value)
    module: Optional[str] = Field(default=None)
    deep_link: Optional[str] = Field(default=None)
    linked_entity_id: Optional[str] = Field(default=None)
    linked_status: Optional[str] = Field(default=None)

    # File "attach" is stubbed — filename only, no real file storage (see plan generation logic).
    attachment_filename: Optional[str] = Field(default=None)
    attachment_url: Optional[str] = Field(default=None)

    position: int = Field(default=0)


class PlanAction(PlanActionBase, table=True):
    __tablename__ = 'plan_action'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class PlanDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: PlanBase) -> Plan:
        new_plan = Plan(**data.model_dump())
        self.session.add(new_plan)
        await self.session.commit()
        await self.session.refresh(new_plan)
        return new_plan

    async def get_by_case(self, case_id: UUID) -> Optional[Plan]:
        result = await self.session.execute(select(Plan).where(Plan.case_id == case_id))
        return result.scalars().first()

    async def update(self, plan_id: UUID, **kwargs) -> Optional[Plan]:
        kwargs['modified'] = kwargs.get('modified') or get_utc_now(tz=False)
        statement = (
            update(Plan).
            returning(Plan).
            where(Plan.id == plan_id).
            values(**kwargs)
        )
        result = await self.session.execute(statement=statement)
        await self.session.commit()
        return result.scalars().first()


class PlanWeekDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_create(self, data: List[PlanWeekBase]) -> List[PlanWeek]:
        new_rows = [PlanWeek(**item.model_dump()) for item in data]
        self.session.add_all(new_rows)
        await self.session.commit()
        for row in new_rows:
            await self.session.refresh(row)
        return new_rows

    async def list_by_plan(self, plan_id: UUID) -> List[PlanWeek]:
        result = await self.session.execute(
            select(PlanWeek).where(PlanWeek.plan_id == plan_id).order_by(PlanWeek.position.asc())
        )
        return result.scalars().all()

    async def delete_by_plan(self, plan_id: UUID) -> None:
        rows = await self.list_by_plan(plan_id)
        for row in rows:
            await self.session.delete(row)
        await self.session.commit()

    async def update(self, week_id: UUID, **kwargs) -> Optional[PlanWeek]:
        kwargs['modified'] = kwargs.get('modified') or get_utc_now(tz=False)
        statement = (
            update(PlanWeek).
            returning(PlanWeek).
            where(PlanWeek.id == week_id).
            values(**kwargs)
        )
        result = await self.session.execute(statement=statement)
        await self.session.commit()
        return result.scalars().first()


class PlanActionDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_create(self, data: List[PlanActionBase]) -> List[PlanAction]:
        new_rows = [PlanAction(**item.model_dump()) for item in data]
        self.session.add_all(new_rows)
        await self.session.commit()
        for row in new_rows:
            await self.session.refresh(row)
        return new_rows

    async def get_by_id(self, action_id: UUID) -> Optional[PlanAction]:
        result = await self.session.execute(select(PlanAction).where(PlanAction.id == action_id))
        return result.scalars().first()

    async def list_by_plan(self, plan_id: UUID) -> List[PlanAction]:
        result = await self.session.execute(
            select(PlanAction).where(PlanAction.plan_id == plan_id).order_by(PlanAction.position.asc())
        )
        return result.scalars().all()

    async def delete_by_plan(self, plan_id: UUID) -> None:
        rows = await self.list_by_plan(plan_id)
        for row in rows:
            await self.session.delete(row)
        await self.session.commit()

    async def update(self, action_id: UUID, **kwargs) -> Optional[PlanAction]:
        kwargs['modified'] = kwargs.get('modified') or get_utc_now(tz=False)
        statement = (
            update(PlanAction).
            returning(PlanAction).
            where(PlanAction.id == action_id).
            values(**kwargs)
        )
        result = await self.session.execute(statement=statement)
        await self.session.commit()
        return result.scalars().first()
