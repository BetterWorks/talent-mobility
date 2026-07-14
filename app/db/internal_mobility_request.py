from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import ARRAY, Column, Field, SQLModel, Text

from app.db import meta
from app.utils.common import get_utc_now


class InternalMobilityRequestBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    title: str = Field()
    job_description: Optional[str] = Field(default=None)
    seniority_level: Optional[str] = Field(default=None)

    business_unit: Optional[str] = Field(default=None)
    hiring_manager: Optional[str] = Field(default=None)

    min_salary: Optional[Decimal] = Field(default=None)
    max_salary: Optional[Decimal] = Field(default=None)
    budget_currency: Optional[str] = Field(default=None)

    required_skills: Optional[List[str]] = Field(default=None, sa_column=Column(ARRAY(Text)))
    number_of_candidates_to_hire: Optional[int] = Field(default=None)
    hiring_estimate_in_days: Optional[int] = Field(default=None)
    external_hiring_cost: Optional[Decimal] = Field(default=None)

    start_date_target: Optional[date] = Field(default=None)


class InternalMobilityRequest(InternalMobilityRequestBase, table=True):
    __tablename__ = 'internal_mobility_request'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class InternalMobilityRequestDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: InternalMobilityRequestBase) -> InternalMobilityRequest:
        new_request = InternalMobilityRequest(**data.model_dump())
        self.session.add(new_request)
        await self.session.commit()
        await self.session.refresh(new_request)
        return new_request

    async def get_by_id(self, request_id: UUID) -> Optional[InternalMobilityRequest]:
        result = await self.session.execute(
            select(InternalMobilityRequest).where(InternalMobilityRequest.id == request_id)
        )
        return result.scalars().first()

    async def list(
        self,
        business_unit: Optional[str] = None,
        hiring_manager: Optional[str] = None,
        seniority_level: Optional[str] = None,
    ) -> List[InternalMobilityRequest]:
        result = await self.session.execute(
            select(InternalMobilityRequest).where(
                True if business_unit is None else InternalMobilityRequest.business_unit == business_unit,
                True if hiring_manager is None else InternalMobilityRequest.hiring_manager == hiring_manager,
                True if seniority_level is None else InternalMobilityRequest.seniority_level == seniority_level,
            ).order_by(InternalMobilityRequest.created.desc())
        )
        return result.scalars().all()
