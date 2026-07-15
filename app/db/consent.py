from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, Field, SQLModel

from app.db import meta
from app.utils.common import get_utc_now


class ConsentType(str, Enum):
    CONSENT = 'consent'
    RELEASE = 'release'
    CONFIRMATION = 'confirmation'
    POLICY = 'policy'


class ConsentStatus(str, Enum):
    NOT_REQUESTED = 'notrequested'
    REQUESTED = 'requested'
    RECEIVED = 'received'
    DECLINED = 'declined'
    BLOCKED = 'blocked'


class ConsentParticipantRole(str, Enum):
    CANDIDATE = 'candidate'
    CURRENT_MANAGER = 'current_manager'
    HIRING_MANAGER = 'hiring_manager'
    HRBP = 'hrbp'


class ConsentBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    # Logical ref: better_sense.mobility_case.id
    case_id: UUID = Field()

    # Participant identity is denormalized here rather than referencing an external user id:
    # candidate resolves via candidate_profile.user_uuid + user_directory, but current_manager/
    # hiring_manager are plain display-name strings on role_request/HRIS, not real user
    # references, so there's nothing else to join against.
    participant_role: str = Field()
    participant_name: Optional[str] = Field(default=None)
    role_label: Optional[str] = Field(default=None)
    designation: Optional[str] = Field(default=None)

    consent_type: str = Field()
    status: str = Field(default=ConsentStatus.NOT_REQUESTED.value)
    deadline: Optional[date] = Field(default=None)
    requested_on: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    last_reminder_on: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    received_on: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    received_by_hr: bool = Field(default=False)
    escalated: bool = Field(default=False)
    reason_code: Optional[str] = Field(default=None)


class Consent(ConsentBase, table=True):
    __tablename__ = 'consent'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class ConsentDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_create(self, data: List[ConsentBase]) -> List[Consent]:
        new_rows = [Consent(**item.model_dump()) for item in data]
        self.session.add_all(new_rows)
        await self.session.commit()
        for row in new_rows:
            await self.session.refresh(row)
        return new_rows

    async def get_by_id(self, consent_id: UUID) -> Optional[Consent]:
        result = await self.session.execute(select(Consent).where(Consent.id == consent_id))
        return result.scalars().first()

    async def list_by_case(self, case_id: UUID) -> List[Consent]:
        result = await self.session.execute(
            select(Consent).where(Consent.case_id == case_id).order_by(Consent.created.asc())
        )
        return result.scalars().all()

    async def update(self, consent_id: UUID, **kwargs) -> Optional[Consent]:
        kwargs['modified'] = kwargs.get('modified') or get_utc_now(tz=False)
        statement = (
            update(Consent).
            returning(Consent).
            where(Consent.id == consent_id).
            values(**kwargs)
        )
        result = await self.session.execute(statement=statement)
        await self.session.commit()
        return result.scalars().first()
