from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, SQLModel

from app.db import meta


class UsersHrisDetailsBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)

    user_uuid: UUID = Field()
    org_uuid: UUID = Field()
    org_id: Optional[int] = Field(default=None)
    user_id: Optional[int] = Field(default=None)

    current_salary: Optional[Decimal] = Field(default=None)
    hike_given_on: Optional[date] = Field(default=None)
    hike_percentage: Optional[Decimal] = Field(default=None)

    department: Optional[str] = Field(default=None)
    location: Optional[str] = Field(default=None)
    start_date: Optional[date] = Field(default=None)
    current_manager: Optional[str] = Field(default=None)
    job_level: Optional[str] = Field(default=None)


class UsersHrisDetails(UsersHrisDetailsBase, table=True):
    __tablename__ = 'users_hris_details'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class UsersHrisDetailsDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: UsersHrisDetailsBase) -> UsersHrisDetails:
        new_details = UsersHrisDetails(**data.model_dump())
        self.session.add(new_details)
        await self.session.commit()
        await self.session.refresh(new_details)
        return new_details

    async def get_by_user_and_org(self, user_uuid: UUID, org_uuid: UUID) -> Optional[UsersHrisDetails]:
        result = await self.session.execute(
            select(UsersHrisDetails).where(
                UsersHrisDetails.user_uuid == user_uuid,
                UsersHrisDetails.org_uuid == org_uuid,
            )
        )
        return result.scalars().first()

    async def get_by_users(self, user_uuids: List[UUID], org_uuid: UUID) -> List[UsersHrisDetails]:
        result = await self.session.execute(
            select(UsersHrisDetails).where(
                UsersHrisDetails.user_uuid.in_(user_uuids),
                UsersHrisDetails.org_uuid == org_uuid,
            )
        )
        return result.scalars().all()
